"""손님 말 → 의도(intent)와 메뉴·옵션 찾기.

C안 (PM 결정 2026-10-19): 규칙 먼저, 못 알아들을 때만 LLM.
1) 아래 규칙으로 먼저 판단한다 (빠르고 결과가 항상 같음).
2) 규칙이 뜻을 못 잡으면 모델 서버 POST /nlu (LLM)가 손님 말을 표준 문장으로 다시 쓰고, 그 문장을 다시 규칙으로 읽는다.
   모델 서버에 API 키가 없거나 실패하면 규칙 결과 그대로 ("다시 말씀해 주세요").
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
MODEL_TIMEOUT_SEC = float(os.getenv("NLU_TIMEOUT_SEC", "8"))  # LLM 다시 쓰기는 못 알아들은 말에만 쓰므로 조금 넉넉히
MODEL_MIN_CONFIDENCE = 0.5
MODEL_RETRY_AFTER_SEC = 60  # 모델 서버가 실패하면 이 시간 동안은 바로 규칙을 쓴다

INTENTS = {
    "ADD_ITEM", "REMOVE_ITEM", "CHANGE_QTY", "CHANGE_OPTION", "ASK_MENU", "RECOMMEND", "VIEW_CART",
    "CHECKOUT", "CONFIRM", "DENY", "RESTART", "CANCEL_ORDER", "CALL_STAFF", "UNKNOWN",
    # 화면 조작 (말로 쪽 넘기기·메뉴판 보기·다시 듣기)
    "PAGE_NEXT", "PAGE_PREV", "SHOW_MENU", "CLOSE_MENU", "REPEAT",
    "UNDO",  # "잘못 말했어", "전으로 돌아가 줘": 방금 한 것 되돌리기
    # 어르신 손님이 자주 하는 말
    "SPEAK_SLOWER", "SPEAK_FASTER", "SPEAK_LOUDER", "TOTAL_PRICE", "CLEAR_CART", "WAIT", "SMALLTALK",
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
    category: str | None = None  # "음료 뭐 있어", "다른 햄버거 보여 줘" → 메뉴판 종류 (버거·사이드·음료·디저트)
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


# 학습한 음성 인식 모델은 숫자를 한글로 적는다 ("두 개", "여섯 개")
_QTY_WORDS = [
    ("다섯", 5), ("여섯", 6), ("일곱", 7), ("여덟", 8), ("아홉", 9), ("하나", 1), ("한", 1), ("둘", 2), ("두", 2),
    ("셋", 3), ("세", 3), ("넷", 4), ("네", 4), ("열", 10),
]
_NUM = r"(\d+|다섯|여섯|일곱|여덟|아홉|하나|한|둘|두|셋|세|넷|네|열)"


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


# 화면 조작 말 (띄어쓰기는 norm 에서 지워짐). 메뉴·옵션 이름이 함께 나오면 주문으로 본다
REPEAT_WORDS = ("다시말해", "다시한번말해", "다시얘기", "다시읽어", "한번더말해", "뭐라고", "뭐라구", "뭐라는", "못들었", "못알아들")
SLOWER_WORDS = ("천천히말", "천천히얘기", "천천히읽", "천천히좀", "너무빨라", "빨라요", "빠르다", "빨라서")
FASTER_WORDS = ("빨리말", "빠르게말", "빨리읽", "말이느려", "너무느려", "느려요")
LOUDER_WORDS = ("크게말", "크게얘기", "크게읽", "소리크게", "소리좀크게", "안들려", "잘안들", "소리가작")
CLEAR_WORDS = ("다빼", "전부빼", "모두빼", "다지워", "전부지워", "싹지워", "모두지워", "비워", "다없애", "전부없애")
WAIT_WORDS = ("잠깐만", "잠시만", "기다려", "생각좀", "생각해볼", "고민좀", "고민해볼", "천천히고를", "천천히볼")
SMALLTALK_WORDS = ("안녕", "고마워", "고맙", "감사", "수고")
PREV_WORDS = ("이전페이지", "이전쪽", "이전장", "앞쪽", "앞페이지", "앞장", "처음음료")  # 쪽을 분명히 말할 때만 (그냥 "뒤로" 는 되돌리기)
UNDO_WORDS = ("잘못말", "잘못했", "잘못눌", "잘못들어", "잘못시켰", "잘못골랐", "전으로", "전단계", "뒤로", "되돌려", "되돌리",
              "돌아가", "돌아갈", "방금거취소", "방금거빼", "방금취소", "아까로", "무르", "물러")
NEXT_WORDS = ("다음", "넘겨", "넘어가", "다른거", "다른것", "더보여", "더있", "다른음료", "다른메뉴", "다른햄버거", "다른버거",
              "다른디저트", "다른사이드", "딴거")
SHOW_WORDS = ("메뉴판", "메뉴보여", "메뉴좀보여", "뭐있", "뭐가있", "종류", "보여줘", "보여주", "보여달", "볼래", "보고싶")
CLOSE_WORDS = ("닫아", "닫기", "그만볼", "메뉴판그만", "안볼래")
CATEGORY_WORDS = {"버거": ("햄버거", "버거"), "사이드": ("사이드", "감자", "곁들"), "음료": ("음료", "마실", "드링크", "음료수"),
                  "디저트": ("디저트", "후식", "아이스크림", "달달")}


def _screen_intent(t: str, p: Parsed) -> str | None:
    if _has(t, ("바꿔", "바꿀", "바꾸")):
        return None  # "다른 거로 바꿔 주세요" 는 수정 (DENY·CHANGE_OPTION 규칙으로)
    p.category = next((c for c, words in CATEGORY_WORDS.items() if _has(t, words)), None)
    if _has(t, REPEAT_WORDS):
        return "REPEAT"
    if _has(t, CLOSE_WORDS):
        return "CLOSE_MENU"
    if _has(t, PREV_WORDS):
        return "PAGE_PREV"
    if _has(t, NEXT_WORDS):
        return "PAGE_NEXT"  # "다른 음료 보여 줘": 세트 음료 화면이면 다음 쪽, 메뉴 화면이면 메뉴판(dialog 에서 정함)
    if _has(t, ("메뉴판",)) or (_has(t, SHOW_WORDS) and (p.category or _has(t, ("메뉴",)))):
        return "SHOW_MENU"
    return None


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
    if p.options and _has(t, ("바꿔", "바꾸", "변경")):  # "사이드 너겟으로 바꿔 주세요"
        return "CHANGE_OPTION"
    if has_m and _has(t, ("빼", "삭제", "없애", "지워")):
        return "REMOVE_ITEM"
    # 안내 빠르기·크기는 옵션 이름이 섞여도("크게 말해" 의 "크게" = 라지 별명) 먼저 본다
    for intent, words in (("SPEAK_SLOWER", SLOWER_WORDS), ("SPEAK_FASTER", FASTER_WORDS), ("SPEAK_LOUDER", LOUDER_WORDS)):
        if _has(t, words) and not p.menus:
            return intent
    if not has_m:
        for intent, words in (("CLEAR_CART", CLEAR_WORDS), ("UNDO", UNDO_WORDS)):
            if _has(t, words):
                return intent  # "방금 거 취소" 는 주문 전체 취소가 아니라 되돌리기(UNDO)
        if "얼마" in t:
            return "TOTAL_PRICE"  # 메뉴 이름 없이 "다 해서 얼마예요?" → 장바구니 합계
        if _has(t, WAIT_WORDS):
            return "WAIT"
    if "취소" in t and not has_m:
        return "CANCEL_ORDER"
    if not has_m and (screen := _screen_intent(t, p)):
        return screen
    if _has(t, ("추천", "뭐가맛있", "맛있는거", "뭐먹지", "골라줘", "인기")):
        return "RECOMMEND"
    if p.menus and _has(t, ("얼마", "칼로리", "kcal", "알레르기", "매워", "매운가", "맵나", "뭐들어", "들어가", "들었", "뭐예요", "뭐에요")):
        return "ASK_MENU"
    if _has(t, ("뭐담", "장바구니", "주문내역", "뭐시켰", "뭐주문")):
        return "VIEW_CART"
    if re.search(r"더(줘|주세요|요|$)", t):
        m = re.search(_NUM + r"(개|잔)?더", t)
        p.qty_delta = _number_at(m.group(1)) if m else 1
        return "CHANGE_QTY"
    if has_m:
        m = re.search(_NUM + r"(개|잔)?(로|만)", t)
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
    if _has(t, SMALLTALK_WORDS):
        return "SMALLTALK"  # 인사·고맙다는 말 → "다시 말씀해 주세요" 대신 인사로 받고 안내를 이어 감
    return "UNKNOWN"


_model_down_until = 0.0


def _model_rewrite(text: str, catalog: Catalog, context: dict) -> str | None:
    """모델 서버 /nlu(LLM)에게 손님 말을 키오스크가 아는 표준 문장으로 다시 써 달라고 한다. 실패하면 None."""
    global _model_down_until
    if time.monotonic() < _model_down_until:
        return None
    payload = {
        "text": text,
        **context,
        "menus": [m.name for m in catalog.menus.values()],
        "options": sorted({o.name for o in catalog.options.values()}),
    }
    try:
        r = httpx.post(f"{MODEL_URL}/nlu", json=payload, timeout=MODEL_TIMEOUT_SEC)
        r.raise_for_status()
        body = r.json()
        if float(body.get("confidence", 0)) < MODEL_MIN_CONFIDENCE:
            return None
        return (body.get("rewrite") or "").strip() or None
    except (httpx.HTTPError, ValueError, TypeError):
        # API 키가 없거나(503) LLM이 실패하면 잠시 규칙만 쓴다 (손님을 매번 기다리게 하지 않게)
        _model_down_until = time.monotonic() + MODEL_RETRY_AFTER_SEC
        return None


def parse(text: str, catalog: Catalog, context: dict | None = None, _rewritten: bool = False) -> Parsed:
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

    # C안: 규칙이 못 알아들었을 때만 LLM(모델 서버 /nlu)에게 표준 문장으로 다시 써 달라고 한 뒤, 그 문장을 다시 규칙으로 읽는다.
    # LLM 결과도 메뉴 DB·규칙을 거치므로 없는 메뉴가 담기지 않는다. 실패하면 지금처럼 "다시 말씀해 주세요".
    if not _rewritten and _needs_help(p):
        rewritten = _model_rewrite(text, catalog, context or {})
        if rewritten and norm(rewritten) != t:
            q = parse(rewritten, catalog, context, _rewritten=True)
            if not _needs_help(q):
                q.text, q.source = text, f"llm:{rewritten}"
                return q
    return p


def _needs_help(p: Parsed) -> bool:
    """규칙이 뜻을 못 잡은 경우: 의도를 모르거나("다시 말씀해 주세요"), "~주세요"인데 메뉴를 못 찾았거나("그 메뉴는 없어요"),
    담기·빼기·바꾸기라면서 대상(메뉴·옵션·수량)을 못 찾은 경우."""
    if p.intent in {"UNKNOWN", "UNKNOWN_MENU"}:
        return True
    found = p.menus or p.options or p.dine_type or p.set_choice is not None or p.qty_delta or p.qty_absolute
    return p.intent in {"ADD_ITEM", "REMOVE_ITEM", "CHANGE_OPTION", "CHANGE_QTY"} and not found


def similar_menu(text: str, catalog: Catalog) -> MenuItem | None:
    """메뉴에 없는 걸 말했을 때 비슷한 메뉴 하나를 고른다 (글자가 가장 많이 겹치는 메뉴)."""
    t = norm(text)
    best, best_score = None, 0
    for key, menu_id in catalog.menu_keys:
        score = sum(1 for ch in set(key) if ch in t)
        if score > best_score and score >= 2:
            best, best_score = catalog.menus[menu_id], score
    return best
