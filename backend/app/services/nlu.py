"""손님 말 → 의도(intent)와 메뉴·옵션 찾기.

1) 모델 서버의 POST /nlu 가 있으면 의도는 모델 결과를 쓴다 (노션 API 명세 "모델 입출력 형식").
2) 모델 서버가 없거나 실패하면 아래 규칙으로 판단한다. 지금은 모델 서버에 /nlu 가 없어서 규칙을 쓴다.
메뉴·옵션 이름 찾기는 항상 백엔드가 메뉴 DB와 별명으로 한다.
"""
import os
import re
import time
from dataclasses import dataclass, field

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..models import MenuItem, OptionItem
from ..seed import OPTION_ALIASES

MODEL_URL = os.getenv("MODEL_URL", "http://localhost:8001")
MODEL_TIMEOUT_SEC = 3.0
MODEL_RETRY_AFTER_SEC = 60  # 모델 서버가 실패하면 이 시간 동안은 바로 규칙을 쓴다

INTENTS = {
    "ADD_ITEM", "REMOVE_ITEM", "CHANGE_QTY", "CHANGE_OPTION", "ASK_MENU", "RECOMMEND", "VIEW_CART",
    "CHECKOUT", "CONFIRM", "DENY", "RESTART", "CANCEL_ORDER", "CALL_STAFF", "UNKNOWN",
}

_STRIP = re.compile(r"[\s.,!?~·'\"()\[\]+\-]")


def norm(text: str) -> str:
    return _STRIP.sub("", text).lower()


def _base_name(name: str) -> str:
    return re.sub(r"\s*\(.*?\)", "", name)


@dataclass
class Mention:
    kind: str  # menu, option
    ref_id: int
    start: int
    end: int
    quantity: int | None = None
    is_set: bool | None = None


@dataclass
class Parsed:
    text: str
    intent: str
    menus: list[Mention] = field(default_factory=list)
    options: list[Mention] = field(default_factory=list)
    dine_type: str | None = None
    set_choice: bool | None = None
    qty_delta: int | None = None  # "하나 더" → +1
    qty_absolute: int | None = None  # "하나만", "두 개로" → 그 수량
    source: str = "rules"


class Catalog:
    """메뉴·옵션 이름과 별명 목록 (긴 이름부터 찾아야 '더블 불고기'가 '불고기'보다 먼저 잡힌다)."""

    def __init__(self, db: Session):
        menus = db.scalars(select(MenuItem).options(selectinload(MenuItem.aliases))).all()
        self.menus = {m.id: m for m in menus}
        keys = []
        for m in menus:
            for word in {m.name, _base_name(m.name), *(a.alias for a in m.aliases)}:
                keys.append((norm(word), m.id))
        self.menu_keys = sorted(set(keys), key=lambda k: -len(k[0]))

        options = db.scalars(select(OptionItem)).all()
        self.options = {o.id: o for o in options}
        okeys = []
        for o in options:
            for word in {o.name, *OPTION_ALIASES.get(o.name, [])}:
                okeys.append((norm(word), o.id))
        self.option_keys = sorted(set(okeys), key=lambda k: -len(k[0]))

    def all_names(self) -> list[tuple[str, int]]:
        return self.menu_keys


def _find(text: str, keys: list[tuple[str, int]], kind: str) -> list[Mention]:
    taken = [False] * len(text)
    found = []
    for key, ref_id in keys:
        if not key:
            continue
        start = text.find(key)
        while start != -1:
            end = start + len(key)
            if not any(taken[start:end]):
                for i in range(start, end):
                    taken[i] = True
                found.append(Mention(kind, ref_id, start, end))
            start = text.find(key, end)
    return sorted(found, key=lambda m: m.start)


_QTY_WORDS = [("다섯", 5), ("하나", 1), ("한", 1), ("둘", 2), ("두", 2), ("셋", 3), ("세", 3), ("넷", 4), ("네", 4)]


def _number_at(text: str) -> int | None:
    m = re.match(r"(\d+)", text)
    if m:
        return int(m.group(1))
    for word, n in _QTY_WORDS:
        if text.startswith(word):
            return n
    return None


_PARTICLES = ("으로", "이랑", "하고", "로", "도", "랑", "는", "은", "를", "을")


def _read_after(text: str, end: int) -> tuple[bool | None, int | None]:
    """메뉴 이름 바로 뒤의 '세트/단품'과 수량을 읽는다. 예: '불고기버거세트하나' → (True, 1)"""
    rest = text[end:end + 12]
    is_set = None
    moved = True
    while moved and rest:
        moved = False
        if rest.startswith("세트"):
            is_set, rest, moved = True, rest[2:], True
        elif rest.startswith("단품"):
            is_set, rest, moved = False, rest[2:], True
        else:
            for particle in _PARTICLES:
                if rest.startswith(particle):
                    rest, moved = rest[len(particle):], True
                    break
    return is_set, _number_at(rest)


def _has(text: str, words) -> bool:
    return any(w in text for w in words)


# 식사 장소: 버튼 글자("매장에서", "포장")뿐 아니라 손님이 실제로 하는 말도 알아듣는다 (띄어쓰기는 norm 에서 지워짐)
DINE_IN_WORDS = ("먹고갈", "먹고가", "여기서", "매장", "안에서", "앉아서", "홀에서")
TAKEOUT_WORDS = (
    "포장", "테이크아웃", "takeout",
    "가져갈", "가져가", "가지고갈", "가지고가", "갖고갈", "갖고가", "들고갈", "들고가",
    "싸주", "싸줘", "싸가", "집에",
)


def _rule_intent(t: str, p: Parsed) -> str:
    has_m = bool(p.menus or p.options)
    if not t:
        return "UNKNOWN"
    if "직원" in t:
        return "CALL_STAFF"
    if _has(t, ("처음으로", "처음부터", "처음화면")):
        return "RESTART"
    if "말고" in t and has_m:
        return "CHANGE_OPTION"
    if has_m and _has(t, ("빼", "삭제", "없애", "지워")):
        return "REMOVE_ITEM"
    if "취소" in t and not has_m:
        return "CANCEL_ORDER"
    if _has(t, ("추천", "뭐가맛있", "맛있는거", "뭐먹지", "골라줘", "인기")):
        return "RECOMMEND"
    if p.menus and _has(t, ("얼마", "칼로리", "kcal", "알레르기", "매워", "매운가", "맵나", "뭐들어", "들어가", "들었", "뭐예요", "뭐에요")):
        return "ASK_MENU"
    if _has(t, ("뭐담", "장바구니", "주문내역", "뭐시켰", "뭐주문")):
        return "VIEW_CART"
    if re.search(r"더(줘|주세요|요|$)", t):
        m = re.search(r"(\d+|한|두|세|네)(개|잔)더|(하나|둘|셋|넷)더", t)
        p.qty_delta = _number_at(m.group(1) or m.group(3)) if m else 1
        return "CHANGE_QTY"
    if has_m:
        m = re.search(r"(\d+|하나|한|두|세|네)(개|잔)?(로|만)", t)
        if m:
            p.qty_absolute = _number_at(m.group(1))
            return "CHANGE_QTY"
        return "ADD_ITEM"
    if _has(t, ("아니", "아뇨", "싫어", "없어", "없이", "없습", "수정", "바꿀", "틀려")):
        return "DENY"
    if t.startswith(("응", "네", "예", "맞아", "맞습", "좋아", "그래", "오케이", "ok", "있어", "있습", "담아", "기본")) or _has(
        t, ("쿠폰있", "다시결제", "다시할", "부탁", "맞아요")
    ):
        return "CONFIRM"
    if _has(t, ("주문할게", "주문할께", "주문할래", "결제", "계산", "다골랐", "이대로", "이게다", "그게다", "주문완료")):
        return "CHECKOUT"
    if p.set_choice is not None or p.dine_type is not None:
        return "ANSWER"  # "세트", "단품", "매장에서", "포장" 같은 짧은 대답
    if _has(t, ("주세요", "줘", "주문", "시킬", "먹을래", "먹고싶")):
        return "UNKNOWN_MENU"
    return "UNKNOWN"


_model_down_until = 0.0


def _model_intent(text: str, context: dict) -> tuple[str, float] | None:
    global _model_down_until
    if time.monotonic() < _model_down_until:
        return None
    try:
        r = httpx.post(f"{MODEL_URL}/nlu", json={"text": text, **context}, timeout=MODEL_TIMEOUT_SEC)
        r.raise_for_status()
        body = r.json()
        intent = body.get("intent")
        if intent not in INTENTS:
            return None
        return intent, float(body.get("confidence", 0))
    except (httpx.HTTPError, ValueError):
        _model_down_until = time.monotonic() + MODEL_RETRY_AFTER_SEC
        return None


def parse(text: str, catalog: Catalog, context: dict | None = None) -> Parsed:
    t = norm(text)
    p = Parsed(text=text, intent="UNKNOWN")
    p.menus = _find(t, catalog.menu_keys, "menu")
    p.options = _find(t, catalog.option_keys, "option")
    for m in p.menus:
        m.is_set, m.quantity = _read_after(t, m.end)

    if _has(t, DINE_IN_WORDS):
        p.dine_type = "dine_in"
    elif _has(t, TAKEOUT_WORDS):
        p.dine_type = "takeout"
    if "세트" in t:
        p.set_choice = True
    elif _has(t, ("단품", "버거만", "그것만", "그거만")):
        p.set_choice = False

    p.intent = _rule_intent(t, p)
    model = _model_intent(text, context or {})
    if model and model[1] >= 0.6:
        p.intent, p.source = model[0], "model"
    return p


def similar_menu(text: str, catalog: Catalog) -> MenuItem | None:
    """메뉴에 없는 걸 말했을 때 비슷한 메뉴 하나를 고른다 (글자가 가장 많이 겹치는 메뉴)."""
    t = norm(text)
    best, best_score = None, 0
    for key, menu_id in catalog.menu_keys:
        score = sum(1 for ch in set(key) if ch in t)
        if score > best_score and score >= 2:
            best, best_score = catalog.menus[menu_id], score
    return best
