"""대화형 에이전트: 기획서 "5. 사용자 흐름"(5-1 기본 흐름, 5-2 예외 흐름)을 따라 주문을 진행한다.

단계(step): DINE_TYPE(식사 장소) → MENU(메뉴) → OPTION(세트·음료·사이즈) → CONFIRM(주문 확인)
          → COUPON(쿠폰 확인) → PAYMENT(결제) → DONE
버튼을 누르는 것은 그 버튼 글자를 말한 것과 같게 처리한다 (choices 글자를 그대로 /chat 으로 보내면 된다).
안내 문장(reply_text)은 백엔드 템플릿으로 만든다 (모델이 문장을 만들지는 노션 API 명세 미결 사항).
"""
import copy
import os
import time
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import aware, now_utc
from ..errors import ApiError
from ..models import ConversationLog, Coupon, KioskSession, MenuItem, OptionGroup, Order, StaffCall
from . import cart as cart_svc
from . import nlu
from .pricing import CouponProblem, coupon_discount, recalc

DINE_TYPE, MENU, OPTION, CONFIRM, COUPON, PAYMENT, DONE = (
    "DINE_TYPE", "MENU", "OPTION", "CONFIRM", "COUPON", "PAYMENT", "DONE",
)
EDITABLE_STEPS = (DINE_TYPE, MENU, OPTION, CONFIRM, COUPON, PAYMENT)

# 세트 옵션 중 손님에게 물어보는 순서. 나머지(세트 사이드)는 기본값(후렌치 후라이)으로 둔다.
ASKED_GROUPS = ["세트 음료", "세트 사이즈"]

MSG_RETRY = "다시 한번 말씀해 주세요. 화면의 버튼을 눌러도 돼요."
CHOICE_NO_COUPON = "쿠폰 없이 결제할게요"
CHOICE_STAFF = "직원 불러 주세요"


# ---------- 작은 도우미 ----------

def _has_batchim(word: str) -> bool:
    for ch in reversed(word):
        if "가" <= ch <= "힣":
            return (ord(ch) - 0xAC00) % 28 != 0
        if ch.isdigit():
            return ch in "0136789"
        if ch.isalpha():
            return False
    return False


def josa(word: str, with_batchim: str, without: str) -> str:
    return word + (with_batchim if _has_batchim(word) else without)


def ro(word: str) -> str:
    """'사이다로', '라지로', '셋으로' (받침이 없거나 ㄹ받침이면 '로')"""
    for ch in reversed(word):
        if "가" <= ch <= "힣":
            final = (ord(ch) - 0xAC00) % 28
            return word + ("로" if final in (0, 8) else "으로")
        if ch.isalnum():
            break
    return word + "로"


def _state(session: KioskSession) -> dict:
    # 깊은 복사: 안쪽 목록을 그 자리에서 고치면 DB가 바뀐 줄 모르고 저장하지 않는다
    state = copy.deepcopy(session.dialog_state or {})
    state.setdefault("drafts", [])
    state.setdefault("fail_count", 0)
    state.setdefault("coupon_fail_count", 0)
    return state


def _save(session: KioskSession, state: dict) -> None:
    session.dialog_state = state  # 새 dict 를 넣어야 변경이 저장된다
    session.last_active_at = now_utc()


def _items_sentence(order: Order) -> str:
    parts = [f"{cart_svc.item_label(i)} {cart_svc.count_word(i.quantity)}" for i in order.items]
    return ", ".join(parts)


# ---------- 메뉴 고르는 중(draft) ----------

def _draft_need(db: Session, draft: dict):
    """아직 정하지 않은 것: ('SET', None) / ('GROUP', 옵션그룹) / None(다 정함)"""
    menu = db.get(MenuItem, draft["menu_id"])
    if menu.set_price is None:
        draft["is_set"] = False
    if draft["is_set"] is None:
        return "SET", None
    groups = cart_svc.applicable_groups(menu, draft["is_set"])
    chosen = draft["options"]
    # 묻지 않는 옵션(세트 사이드)은 장바구니에 넣을 때 기본값으로 채운다 (_fill_defaults)
    for name in ASKED_GROUPS:
        for g in groups:
            if g.name == name and str(g.id) not in chosen:
                return "GROUP", g
    return None


# 화면 구분 값(question): 같은 step 안에서도 어떤 질문인지 프론트가 글자 대신 이 값으로 화면을 고른다
GROUP_QUESTIONS = {"세트 음료": "SET_DRINK", "세트 사이즈": "SET_SIZE", "세트 사이드": "SET_SIDE"}


def _question(db: Session, draft: dict) -> tuple[str, list[str], str]:
    menu = db.get(MenuItem, draft["menu_id"])
    need, group = _draft_need(db, draft)
    if need == "SET":
        return f"{josa(menu.name, '은', '는')} 세트로 드릴까요? 감자튀김과 음료가 같이 나와요.", ["세트", "단품"], "SET_OR_SINGLE"
    default = cart_svc.default_option(group)
    code = GROUP_QUESTIONS.get(group.name, "OPTION")
    if group.name == "세트 사이즈":
        large = next((o for o in group.items if o.extra_price > 0), None)
        extra = f" 라지는 {cart_svc.won(large.extra_price)} 더 내요." if large else ""
        return f"사이즈는 미디엄으로 드릴까요, 라지로 드릴까요?{extra}", [o.name for o in group.items], code
    label = group.name.replace("세트 ", "")
    return f"{josa(label, '은', '는')} 뭐로 드릴까요? 기본은 {josa(default.name, '이에요', '예요')}.", [o.name for o in group.items], code


def _new_draft(menu: MenuItem, quantity: int | None, is_set: bool | None) -> dict:
    return {"menu_id": menu.id, "quantity": quantity or 1, "is_set": False if menu.set_price is None else is_set, "options": {}}


def _set_groups(db: Session, draft: dict) -> dict[int, object]:
    """이 메뉴(세트)에서 고를 수 있는 옵션 그룹 {그룹 id: 그룹}"""
    menu = db.get(MenuItem, draft["menu_id"])
    if not draft.get("is_set"):
        return {}
    return {g.id: g for g in cart_svc.applicable_groups(menu, True)}


def _take_options(db: Session, draft: dict, p: nlu.Parsed, catalog: nlu.Catalog, after: int = -1) -> list[str]:
    """말 속의 옵션 이름(라지, 너겟, 제로콜라 등)을 고르는 중인 세트에 넣는다.

    지금 묻는 질문이 아니어도 미리 말한 옵션은 기억한다 (예: 음료를 묻는데 "라지로 주세요").
    옵션으로 쓴 글자와 겹치는 메뉴 이름(예: 감자튀김 → 후렌치 후라이 단품)은 따로 담지 않도록 지운다.
    """
    groups = _set_groups(db, draft)
    taken = []
    for opt in p.options:
        if opt.start < after:
            continue
        option = catalog.options[opt.ref_id]
        if option.option_group_id not in groups or str(option.option_group_id) in draft["options"]:
            continue
        draft["options"][str(option.option_group_id)] = option.id
        p.menus = [m for m in p.menus if not (m.start < opt.end and opt.start < m.end)]
        taken.append(f"{groups[option.option_group_id].name.replace('세트 ', '')}는 {ro(option.name)}")
    return taken


def _fill_defaults(db: Session, draft: dict) -> None:
    for g in _set_groups(db, draft).values():
        if g.is_required and str(g.id) not in draft["options"]:
            draft["options"][str(g.id)] = cart_svc.default_option(g).id


def _flush_drafts(db: Session, order: Order, state: dict, notes: list[str]) -> bool:
    """다 정해진 메뉴를 장바구니에 넣는다. 넣은 게 있으면 True"""
    added = False
    remaining = []
    for draft in state["drafts"]:
        if _draft_need(db, draft) is not None:
            remaining.append(draft)
            continue
        _fill_defaults(db, draft)
        item, problem = cart_svc.add_item(
            db, order, draft["menu_id"], draft["quantity"], bool(draft["is_set"]), [int(v) for v in draft["options"].values()]
        )
        notes.append(f"{cart_svc.item_label(item)} {cart_svc.count_word(draft['quantity'])} 담았어요.")
        if problem:
            notes.append(coupon_dropped(problem))
        added = True
    state["drafts"] = remaining
    return added


def _first_incomplete(db: Session, state: dict) -> dict | None:
    for draft in state["drafts"]:
        if _draft_need(db, draft) is not None:
            return draft
    return None


# ---------- 단계별 안내 문장 ----------

def prompt(db: Session, session: KioskSession, order: Order, state: dict) -> tuple[str, list[str], str]:
    """지금 단계의 (안내 문장, 버튼, 화면 구분 값 question)"""
    step = session.step
    if step == OPTION:
        draft = _first_incomplete(db, state)
        if draft:
            return _question(db, draft)
    if step == DINE_TYPE:
        return "드시고 가세요, 포장하세요?", ["매장에서", "포장"], "DINE_TYPE"
    if step == CONFIRM:
        return f"{_items_sentence(order)}. 모두 {cart_svc.won(order.total_amount)}이에요. 맞으세요?", ["맞아요", "수정할게요"], "CONFIRM"
    if step == COUPON:
        if state.get("awaiting") == "COUPON_SCAN":
            return "휴대폰 바코드를 화면 아래 빛나는 곳에 대 주세요.", [CHOICE_NO_COUPON], "COUPON_SCAN"
        return "앱 쿠폰 있으세요? 있으시면 휴대폰 바코드를 화면 아래 빛나는 곳에 대 주세요.", ["쿠폰 있어요", "없어요"], "COUPON_ASK"
    if step == PAYMENT:
        if state.get("awaiting") == "PAYMENT_RETRY":
            return "결제가 안 됐어요. 다시 해 볼까요, 직원을 불러 드릴까요?", ["다시 결제할게요", CHOICE_STAFF], "PAYMENT_RETRY"
        return f"{cart_svc.won(order.total_amount)} 결제할게요. 카드를 화면 아래 빛나는 곳에 꽂아 주세요.", ["카드 결제"], "PAYMENT"
    if step == DONE:
        number = order.order_number
        if order.status == "cancelled" or number is None:
            return "주문이 끝났어요. 새로 주문하시려면 처음 화면에서 [주문 시작]을 눌러 주세요.", [], "CANCELLED"
        return f"주문번호는 {number}번이에요. 화면에 번호가 뜨면 카운터에서 받아 가세요.", [], "DONE"
    # MENU
    recommended = [m.name for m in db.scalars(select(MenuItem).where(MenuItem.is_recommended).order_by(MenuItem.id))]
    if not order.items:
        return "어떤 걸 드시고 싶으세요? 고르기 어려우시면 추천해 드릴게요.", recommended + ["추천해 주세요"], "MENU"
    return "더 필요하신 건 있으세요? 다 고르셨으면 '주문할게요'라고 말씀해 주세요.", ["주문할게요", "추천해 주세요"], "MENU_MORE"


def choice_items(db: Session, choices: list[str], question: str | None) -> list[dict]:
    """버튼마다 화면에 쓸 정보: 메뉴 버튼은 menu_id·가격·사진, 세트 옵션 버튼은 option_item_id·추가 금액."""
    group_name = next((name for name, code in GROUP_QUESTIONS.items() if code == question), None)
    options = {}
    if group_name:
        group = db.scalar(select(OptionGroup).where(OptionGroup.name == group_name))
        options = {o.name: o for o in group.items} if group else {}
    menus = {m.name: m for m in db.scalars(select(MenuItem).where(MenuItem.name.in_(choices)))} if choices else {}
    items = []
    for label in choices:
        if label in options:
            o = options[label]
            items.append({"label": label, "option_item_id": o.id, "extra_price": o.extra_price})
        elif label in menus:
            m = menus[label]
            items.append({"label": label, "menu_id": m.id, "price": m.price, "set_price": m.set_price,
                          "image_url": m.image_url, "sold_out": not m.is_available})
        else:
            items.append({"label": label})
    return items


def response(db: Session, session: KioskSession, order: Order, state: dict, notes: list[str] | None = None,
             intent: str | None = None, actions: list | None = None, transcript: str | None = None,
             override: tuple | list | None = None) -> dict:
    db.flush()  # 새로 담은 항목의 id 를 응답에 넣기 위해
    text, choices, *rest = override or prompt(db, session, order, state)
    question = rest[0] if rest else None
    body = {
        "session_id": session.id,
        "step": session.step,
        "question": question,
        "awaiting": state.get("awaiting"),
        "intent": intent,
        "actions": actions or [],
        "reply_text": " ".join([*(notes or []), text]).strip(),
        "choices": choices,
        "choice_items": choice_items(db, choices, question),
        "cart": cart_svc.cart_view(order),
    }
    if transcript is not None:
        body["transcript"] = transcript
    return body


# ---------- 쿠폰 ----------

_COUPON_MESSAGES = {
    "COUPON_EXPIRED": "기간이 끝난 쿠폰이에요.",
    "COUPON_NOT_STARTED": "아직 쓸 수 없는 쿠폰이에요.",
    "COUPON_ALREADY_USED": "이미 사용한 쿠폰이에요.",
    "COUPON_NOT_APPLICABLE": "이 주문에는 쓸 수 없는 쿠폰이에요.",
}


def coupon_dropped(problem: CouponProblem) -> str:
    return f"주문이 바뀌어서 '{problem.coupon.name}' 쿠폰 조건이 맞지 않아 쿠폰을 뺐어요."


def apply_coupon(db: Session, session: KioskSession, order: Order, state: dict, barcode: str) -> tuple[list[str], tuple | None]:
    """쿠폰을 적용한다. (안내 문장들, 선택지 덮어쓰기) 를 돌려준다."""
    coupon = db.scalar(select(Coupon).where(Coupon.barcode == barcode.strip()))
    if coupon is None:
        state["coupon_fail_count"] += 1
        state["awaiting"] = "COUPON_SCAN"
        if state["coupon_fail_count"] >= 2:
            return [], ("쿠폰을 읽지 못했어요. 쿠폰 없이 결제할까요, 직원을 불러 드릴까요?", [CHOICE_NO_COUPON, CHOICE_STAFF], "COUPON_READ_FAILED_TWICE")
        return [], ("쿠폰을 읽지 못했어요. 화면 밝기를 높이고 다시 대 주세요.", [CHOICE_NO_COUPON], "COUPON_READ_FAILED")

    taken = _coupon_holder(db, coupon, order)
    try:
        if taken is not None:
            raise CouponProblem("COUPON_ALREADY_USED", coupon)
        coupon_discount(coupon, order, now_utc())
    except CouponProblem as exc:
        state["awaiting"] = None
        if exc.code == "COUPON_MENU_MISSING":
            target = coupon.target_menu
            label = target.name + (" 세트" if coupon.target_set_only else "")
            state["awaiting"] = "ADD_COUPON_MENU"
            state["offer_coupon_id"] = coupon.id
            return [f"이 쿠폰은 {label}에 쓰는 쿠폰이에요."], ("쿠폰 메뉴를 담아 드릴까요?", ["담아 주세요", CHOICE_NO_COUPON], "COUPON_ADD_MENU")
        if exc.code == "COUPON_MIN_AMOUNT":
            msg = f"{cart_svc.won(coupon.min_order_amount)} 이상 주문해야 쓸 수 있는 쿠폰이에요."
        else:
            msg = _COUPON_MESSAGES.get(exc.code, _COUPON_MESSAGES["COUPON_NOT_APPLICABLE"])
        return [msg], ("쿠폰 없이 결제할까요?", [CHOICE_NO_COUPON, CHOICE_STAFF], "COUPON_UNUSABLE")

    order.coupon = coupon
    recalc(order, now_utc())
    state["awaiting"] = None
    state.pop("pending_coupon_id", None)
    session.step = PAYMENT
    return [f"'{coupon.name}' 쿠폰을 적용했어요. {cart_svc.won(order.discount_amount)} 할인돼요."], None


# ---------- 주문 확정 (주문 확인에 "맞아요") ----------

def confirm_order(db: Session, session: KioskSession, order: Order, state: dict) -> list[str]:
    if _first_incomplete(db, state):
        raise ApiError(409, "INVALID_STATE", "아직 고르는 중인 메뉴가 있습니다")
    if not order.items:
        raise ApiError(400, "EMPTY_CART", "장바구니가 비어 있습니다")
    if order.dine_type is None:
        raise ApiError(409, "DINE_TYPE_REQUIRED", "식사 장소(매장/포장)를 먼저 골라 주세요")
    order.status = "pending_payment"
    state["return_to_confirm"] = False
    if order.coupon is not None:
        session.step = PAYMENT
        return []
    pending = state.get("pending_coupon_id")
    if pending:
        coupon = db.get(Coupon, pending)
        session.step = COUPON
        notes, override = apply_coupon(db, session, order, state, coupon.barcode)
        if override:  # 그래도 못 쓰면 쿠폰 단계에서 안내
            state["override"] = override
        return notes
    session.step = COUPON
    return []


def _staff_call(db: Session, session: KioskSession, state: dict) -> None:
    if state.get("awaiting") == "PAYMENT_RETRY":
        reason = "payment_failed"
    elif session.step == COUPON and state["coupon_fail_count"] >= 2:
        reason = "barcode_failed"
    else:
        reason = "user_request"
    db.add(StaffCall(session=session, reason=reason))


# 아무 반응이 없으면 서버가 세션을 끝내는 시간. 결제 단계는 따로 짧게 둔다 (손님이 결제 화면에서 그냥 떠난 경우)
SESSION_IDLE_LIMIT_SEC = int(os.getenv("SESSION_IDLE_LIMIT_SEC", "300"))
PAYMENT_IDLE_LIMIT_SEC = int(os.getenv("PAYMENT_IDLE_LIMIT_SEC", "180"))


def is_stale(session: KioskSession) -> bool:
    """끝났거나, 손님이 떠난 것으로 보이는 세션"""
    if session.ended_at is not None:
        return True
    limit = PAYMENT_IDLE_LIMIT_SEC if session.step == PAYMENT else SESSION_IDLE_LIMIT_SEC
    return now_utc() - aware(session.last_active_at) > timedelta(seconds=limit)


def expire_session(session: KioskSession, reason: str = "timeout") -> None:
    """세션을 끝내고, 결제 전 주문은 취소해 쿠폰을 풀어 준다."""
    for order in session.orders:
        if order.status in cart_svc.OPEN_STATUSES:
            cancel_order(session, order)
    if session.ended_at is None:
        end_session(session, reason)


def _coupon_holder(db: Session, coupon: Coupon, order: Order) -> Order | None:
    """이 쿠폰을 붙잡고 있는 다른 주문. 떠난 손님의 주문이면 정리하고 None (기획 이슈 #14)"""
    holder = db.scalar(
        select(Order).where(Order.coupon_id == coupon.id, Order.id != order.id, Order.status != "cancelled")
    )
    if holder is not None and holder.status in cart_svc.OPEN_STATUSES and is_stale(holder.session):
        expire_session(holder.session)
        db.flush()
        return None
    return holder


def end_session(session: KioskSession, reason: str) -> None:
    session.ended_at = now_utc()
    session.end_reason = reason
    session.step = DONE


def cancel_order(session: KioskSession, order: Order) -> None:
    if order.status not in cart_svc.OPEN_STATUSES:
        raise ApiError(409, "INVALID_STATE", "결제된 주문은 키오스크에서 취소할 수 없습니다. 직원에게 문의해 주세요")
    for payment in order.payments:
        if payment.status == "pending":
            payment.status = "failed"
            payment.fail_reason = "ORDER_CANCELLED"
    order.status = "cancelled"
    order.coupon = None


# ---------- 장바구니를 바꾸는 말 ----------

def _cart_item_for(order: Order, menu_ids: list[int]):
    for item in reversed(order.items):
        if item.menu_item_id in menu_ids:
            return item
    return None


def _apply_edit(db: Session, session: KioskSession, order: Order, state: dict, p: nlu.Parsed,
                catalog: nlu.Catalog, notes: list[str], actions: list) -> bool:
    """메뉴 추가·삭제·변경을 처리한다. 무언가 바꿨으면 True"""
    changed = False

    def touch():
        nonlocal changed
        if not changed and session.step in (CONFIRM, COUPON, PAYMENT):
            cart_svc.make_editable(order)
            state["return_to_confirm"] = True
            state["awaiting"] = None
        changed = True

    def note_problem(problem):
        if problem:
            notes.append(coupon_dropped(problem))

    if p.intent == "REMOVE_ITEM":
        targets = [m.ref_id for m in p.menus]
        option_ids = {m.ref_id for m in p.options}
        removed = False
        for menu_id in targets:
            item = _cart_item_for(order, [menu_id])
            if item:
                touch()
                label = cart_svc.item_label(item)
                note_problem(cart_svc.remove_item(order, item))
                notes.append(f"{josa(label, '을', '를')} 뺐어요.")
                actions.append({"type": "REMOVE_ITEM", "menu_id": menu_id, "status": "APPLIED"})
                removed = True
        if not removed and option_ids and any(o.option_item_id in option_ids for i in order.items for o in i.options):
            notes.append("세트 구성은 뺄 수 없어요. 다른 것으로 바꿔 드릴까요? 예: '콜라 말고 사이다'")
        elif not removed:
            notes.append("장바구니에 그 메뉴가 없어요.")
        return changed

    if p.intent == "CHANGE_OPTION" and "말고" not in nlu.norm(p.text):
        # "너겟으로 바꿔 주세요": 그 옵션이 있는 세트(가장 최근 것)의 해당 옵션만 바꾼다 (기획 결정: 확인 화면에서 사이드 바꾸기)
        latest = {catalog.options[o.ref_id].option_group_id: o for o in p.options}  # 같은 그룹은 마지막에 말한 것
        for opt in latest.values():
            new_opt = catalog.options[opt.ref_id]
            for item in reversed(order.items):
                if any(o.option.option_group_id == new_opt.option_group_id for o in item.options):
                    if any(o.option_item_id == new_opt.id for o in item.options):
                        notes.append(f"이미 {josa(new_opt.name, '이에요', '예요')}.")
                        break
                    touch()
                    note_problem(cart_svc.update_item(db, order, item, option_ids=[new_opt.id]))
                    group = new_opt.group.name.replace("세트 ", "")
                    notes.append(f"{josa(group, '을', '를')} {ro(new_opt.name)} 바꿨어요.")
                    actions.append({"type": "CHANGE_OPTION", "item_id": item.id, "status": "APPLIED"})
                    break
        if not changed and not notes:
            notes.append("바꿀 세트가 없어요. 예: '사이드 너겟으로 바꿔 주세요'")
        return changed

    if p.intent == "CHANGE_OPTION":  # "A 말고 B"
        t = nlu.norm(p.text)
        cut = t.find("말고")
        before_opts = [m for m in p.options if m.end <= cut]
        after_opts = [m for m in p.options if m.start >= cut]
        if before_opts and after_opts:
            old_opt, new_opt = catalog.options[before_opts[-1].ref_id], catalog.options[after_opts[0].ref_id]
            for item in reversed(order.items):
                if any(o.option_item_id == old_opt.id for o in item.options) and old_opt.option_group_id == new_opt.option_group_id:
                    touch()
                    ids = [new_opt.id if o.option_item_id == old_opt.id else o.option_item_id for o in item.options]
                    note_problem(cart_svc.update_item(db, order, item, option_ids=ids))
                    notes.append(f"{josa(old_opt.name, '을', '를')} {ro(new_opt.name)} 바꿨어요.")
                    actions.append({"type": "CHANGE_OPTION", "item_id": item.id, "status": "APPLIED"})
                    return True
        before_menus = [m for m in p.menus if m.end <= cut]
        after_menus = [m for m in p.menus if m.start >= cut]
        if before_menus and after_menus:
            item = _cart_item_for(order, [before_menus[-1].ref_id])
            new_menu = catalog.menus[after_menus[0].ref_id]
            if item:
                touch()
                quantity = item.quantity
                label = cart_svc.item_label(item)
                note_problem(cart_svc.remove_item(order, item))
                state["drafts"].append(_new_draft(new_menu, quantity, item.is_set if new_menu.set_price else False))
                notes.append(f"{josa(label, '을', '를')} 뺐어요.")
                return True
        notes.append("무엇을 무엇으로 바꿀지 다시 말씀해 주세요. 예: '콜라 말고 사이다'")
        return changed

    if p.intent == "CHANGE_QTY":
        item = _cart_item_for(order, [m.ref_id for m in p.menus]) if p.menus else (order.items[-1] if order.items else None)
        if item is None and p.menus:  # "빅맥 하나만 주세요" 처럼 아직 없는 메뉴 → 새로 담기
            p.intent = "ADD_ITEM"
            for m in p.menus:
                m.quantity = p.qty_absolute or m.quantity
        elif item is None:
            notes.append("장바구니가 비어 있어요.")
            return changed
        else:
            touch()
            quantity = item.quantity + p.qty_delta if p.qty_delta else (p.qty_absolute or item.quantity)
            note_problem(cart_svc.update_item(db, order, item, quantity=quantity))
            notes.append(f"{josa(cart_svc.item_label(item), '을', '를')} {ro(cart_svc.count_word(item.quantity))} 바꿨어요.")
            actions.append({"type": "CHANGE_QTY", "item_id": item.id, "quantity": item.quantity, "status": "APPLIED"})
            return True

    if p.intent == "ADD_ITEM":
        # 세트 버거 뒤에 나온 음료·사이드 이름은 따로 담지 않고 그 세트의 옵션으로 본다 ("빅맥 세트 제로콜라로")
        # "빅맥 세트 라지 제로콜라로"처럼 세트 버거 뒤에 나온 옵션 이름은 그 세트의 옵션으로 본다
        for m in list(p.menus):
            if not any(x is m for x in p.menus):
                continue  # 앞 세트의 옵션으로 이미 쓰였다
            menu = catalog.menus[m.ref_id]
            if not menu.is_available:
                notes.append(f"{josa(menu.name, '은', '는')} 지금 품절이에요.")
                continue
            touch()
            is_set = m.is_set if m.is_set is not None else (p.set_choice if len(p.menus) == 1 else None)
            draft = _new_draft(menu, m.quantity, is_set)
            if draft["is_set"] is None and _mentions_set_option(db, draft, p, catalog, after=m.end):
                draft["is_set"] = True  # "빅맥 라지로" → 세트 옵션을 말했으니 세트
            if draft["is_set"]:
                _take_options(db, draft, p, catalog, after=m.end)
            state["drafts"].append(draft)
            actions.append({"type": "ADD_ITEM", "menu_id": menu.id, "quantity": draft["quantity"], "status": "PENDING"})
        # 메뉴 없이 옵션 이름만 말했으면(예: 세트 고르는 중 "라지") 고르는 중인 메뉴에 넣는다
        if not p.menus and p.options:
            notes.append(MSG_RETRY)
        return changed
    return changed


def _mentions_set_option(db: Session, draft: dict, p: nlu.Parsed, catalog: nlu.Catalog, after: int = -1) -> bool:
    menu = db.get(MenuItem, draft["menu_id"])
    if menu.set_price is None:
        return False
    group_ids = {g.id for g in cart_svc.applicable_groups(menu, True)}
    return any(o.start >= after and catalog.options[o.ref_id].option_group_id in group_ids for o in p.options)


def _answer_option(db: Session, draft: dict, p: nlu.Parsed, catalog: nlu.Catalog) -> tuple[bool, list[str]]:
    """고르는 중인 메뉴에 대한 대답(세트 여부, 음료, 사이즈, 사이드)이면 반영한다. (반영했는지, 미리 받은 옵션 설명)"""
    need, group = _draft_need(db, draft)
    answered = False
    if need == "SET":
        if p.set_choice is not None:
            draft["is_set"] = p.set_choice
        elif p.intent == "CONFIRM":
            draft["is_set"] = True
        elif p.intent == "DENY":
            draft["is_set"] = False
        elif _mentions_set_option(db, draft, p, catalog):
            draft["is_set"] = True  # "라지로 주세요" → 세트로 알아듣는다
        else:
            return False, []
        answered = True
    taken = _take_options(db, draft, p, catalog) if draft["is_set"] else []
    if taken:
        answered = True
    elif need == "GROUP" and p.intent == "CONFIRM":
        draft["options"][str(group.id)] = cart_svc.default_option(group).id
        answered = True
    return answered, taken


def _menu_info(menu: MenuItem) -> str:
    price = f"단품 {cart_svc.won(menu.price)}"
    if menu.set_price:
        price += f", 세트 {cart_svc.won(menu.set_price)}"
    text = f"{josa(menu.name, '은', '는')} {price}이에요."
    if menu.calories_kcal is not None:
        text += f" {menu.calories_kcal}kcal이고,"
    if menu.allergens and menu.allergens != "없음":
        text += f" {josa(menu.allergens, '이', '가')} 들어 있어요."
    else:
        text += " 알레르기 유발 성분은 없어요."
    return text


# ---------- 한 번의 말 처리 ----------

def handle(db: Session, session: KioskSession, text: str, transcript: str | None = None) -> dict:
    started = time.monotonic()
    state = _state(session)
    state.pop("override", None)
    order = cart_svc.open_order(db, session) if session.step != DONE else session.orders[-1]
    catalog = nlu.Catalog(db)
    history = state.get("history", [])
    p = nlu.parse(text, catalog, {"step": session.step, "cart": [cart_svc.item_label(i) for i in order.items], "history": history[-4:]})
    notes: list[str] = []
    actions: list = []
    override = None

    def finish(result: dict) -> dict:
        history.append({"role": "user", "text": text})
        history.append({"role": "agent", "text": result["reply_text"]})
        state["history"] = history[-8:]
        _save(session, state)
        db.add(ConversationLog(
            session_id=session.id, turn_no=len(history) // 2, stt_text=text, intent=p.intent,
            response_text=result["reply_text"], latency_ms=int((time.monotonic() - started) * 1000),
        ))
        return result

    def reply(**kw):
        return finish(response(db, session, order, state, notes=notes, intent=p.intent, actions=actions,
                               transcript=transcript, override=kw.get("override", override or state.get("override"))))

    if session.step == DONE:
        return reply()

    # 언제든 쓸 수 있는 말 (기획서 5-2)
    if p.intent == "CALL_STAFF":
        _staff_call(db, session, state)
        notes.append("직원을 불렀어요. 잠시만 기다려 주세요.")
        return reply()
    if p.intent == "RESTART":
        cart_svc.clear(order)
        order.dine_type = None
        state.update(drafts=[], awaiting=None, return_to_confirm=False, coupon_fail_count=0, fail_count=0)
        state.pop("pending_coupon_id", None)
        session.step = DINE_TYPE
        notes.append("처음부터 다시 할게요.")
        return reply()
    if state.get("awaiting") == "CANCEL_CONFIRM":
        state["awaiting"] = None
        if p.intent in ("CONFIRM", "CANCEL_ORDER"):
            cancel_order(session, order)
            end_session(session, "cancelled")
            return reply(override=("주문을 취소했어요. 이용해 주셔서 고마워요.", [], "CANCELLED"))
        if p.intent == "DENY":
            notes.append("계속 주문할게요.")
            return reply()
    if p.intent == "CANCEL_ORDER":
        state["awaiting"] = "CANCEL_CONFIRM"
        return reply(override=("주문을 취소할까요? 담은 메뉴가 모두 지워져요.", ["네, 취소할게요", "아니요"], "CANCEL_CONFIRM"))

    if p.dine_type and session.step in EDITABLE_STEPS:
        order.dine_type = p.dine_type

    # 쿠폰 단계 (기획서 5-1의 5. 쿠폰 확인)
    if session.step == COUPON and p.intent in ("CONFIRM", "DENY", "CHECKOUT", "ANSWER"):
        if state.get("awaiting") == "ADD_COUPON_MENU" and p.intent == "CONFIRM":
            coupon = db.get(Coupon, state.pop("offer_coupon_id"))
            cart_svc.make_editable(order)
            draft = _new_draft(coupon.target_menu, 1, True if coupon.target_set_only else False)
            state["drafts"].append(draft)
            state.update(pending_coupon_id=coupon.id, return_to_confirm=True, awaiting=None)
            _flush_drafts(db, order, state, notes)
            session.step = OPTION if _first_incomplete(db, state) else CONFIRM
            return reply()
        if p.intent == "CONFIRM" and state.get("awaiting") != "COUPON_SCAN":
            state["awaiting"] = "COUPON_SCAN"
            return reply()
        if p.intent in ("DENY", "CHECKOUT"):
            state["awaiting"] = None
            state.pop("pending_coupon_id", None)
            session.step = PAYMENT
            return reply()

    # 결제 단계
    if session.step == PAYMENT and p.intent in ("CONFIRM", "CHECKOUT", "ANSWER"):
        state["awaiting"] = None
        return reply()
    if session.step in (COUPON, PAYMENT) and p.intent == "DENY":
        cart_svc.make_editable(order)
        state.update(return_to_confirm=True, awaiting=None)
        session.step = MENU
        return reply(override=("어떤 걸 바꿔 드릴까요?", ["주문할게요"], "EDIT"))

    # 주문 확인 단계
    if session.step == CONFIRM and p.intent in ("CONFIRM", "CHECKOUT"):
        notes.extend(confirm_order(db, session, order, state))
        return reply()
    if session.step == CONFIRM and p.intent == "DENY":
        state["return_to_confirm"] = True
        session.step = MENU
        return reply(override=("어떤 걸 바꿔 드릴까요? 예: '콜라 빼줘', '하나 더'", ["주문할게요"], "EDIT"))

    # 고르는 중인 질문에 대한 대답 (세트? 음료? 사이즈?)
    answered = False
    draft = _first_incomplete(db, state)
    if draft is not None:
        answered, taken = _answer_option(db, draft, p, catalog)
        if answered and (p.intent in ("CONFIRM", "DENY", "ANSWER", "UNKNOWN") or not p.menus):
            p.intent = "ANSWER"
        if taken and _draft_need(db, draft) is not None:
            notes.append(f"{', '.join(taken)} 할게요.")  # 미리 말한 옵션을 기억했다고 알려준다

    changed = _apply_edit(db, session, order, state, p, catalog, notes, actions)

    if p.intent == "RECOMMEND":
        menus = db.scalars(select(MenuItem).where(MenuItem.is_recommended).order_by(MenuItem.id)).all()
        names = ", ".join(m.name for m in menus)
        notes.append(f"제가 추천하는 메뉴는 {names}예요. 어떤 걸로 드릴까요?")
        if session.step == DINE_TYPE and order.dine_type:
            session.step = MENU
        override = (" ".join(notes), [m.name for m in menus], "RECOMMEND")
        notes.clear()
    elif p.intent == "ASK_MENU":
        notes.append(" ".join(_menu_info(catalog.menus[m.ref_id]) for m in p.menus))
    elif p.intent == "VIEW_CART":
        notes.append(f"지금 {josa(_items_sentence(order), '이', '가')} 담겨 있어요." if order.items else "아직 담긴 메뉴가 없어요.")
    elif p.intent == "UNKNOWN_MENU":
        similar = nlu.similar_menu(text, catalog)
        notes.append(f"그 메뉴는 없어요. 비슷한 {josa(similar.name, '은', '는')} 어떠세요?" if similar else "그 메뉴는 없어요.")
        if similar:
            override = (" ".join(notes), [similar.name, "추천해 주세요"], "SIMILAR_MENU")
            notes.clear()
    elif p.intent == "UNKNOWN" and not answered and not (p.dine_type and session.step == DINE_TYPE):
        state["fail_count"] += 1
        notes.append(MSG_RETRY)

    added = _flush_drafts(db, order, state, notes)
    want_confirm = p.intent == "CHECKOUT"
    if want_confirm and not order.items and not state["drafts"]:
        notes.append("아직 담긴 메뉴가 없어요.")
        want_confirm = False

    # 다음 단계 정하기
    if _first_incomplete(db, state):
        session.step = OPTION
    elif order.dine_type is None:
        session.step = DINE_TYPE
    elif order.items and (want_confirm or (state.get("return_to_confirm") and (changed or added or answered))):
        session.step = CONFIRM
        state["return_to_confirm"] = False
    elif session.step in (DINE_TYPE, OPTION) or (session.step == CONFIRM and not order.items):
        session.step = MENU
    if override and session.step == OPTION:
        override = None  # 고르는 중인 질문이 먼저다
    if p.intent not in ("UNKNOWN",):
        state["fail_count"] = 0
    return reply()


def start(db: Session, session: KioskSession) -> dict:
    state = _state(session)
    order = cart_svc.open_order(db, session)
    _save(session, state)
    return response(db, session, order, state, notes=["안녕하세요!"])


def current(db: Session, session: KioskSession) -> dict:
    state = _state(session)
    order = cart_svc.open_order(db, session) if session.step != DONE else session.orders[-1]
    return response(db, session, order, state, override=state.get("override"))


def after_cart_change(db: Session, session: KioskSession, order: Order, notes: list[str]) -> dict:
    """버튼으로 장바구니를 바꾼 뒤의 응답 (결제 전 단계였다면 주문 확인으로 돌아간다)."""
    state = _state(session)
    if session.step in (CONFIRM, COUPON, PAYMENT):
        state["awaiting"] = None
        session.step = CONFIRM if order.items else MENU
    elif session.step in (DINE_TYPE, OPTION):
        session.step = MENU if order.dine_type else DINE_TYPE
    _save(session, state)
    return response(db, session, order, state, notes=notes)


def confirm_by_button(db: Session, session: KioskSession) -> dict:
    """화면의 [맞아요] 버튼 = 주문 확정 (POST /api/sessions/{id}/orders)."""
    state = _state(session)
    order = cart_svc.open_order(db, session)
    if session.step in (COUPON, PAYMENT) and order.status == "pending_payment":
        return response(db, session, order, state)  # 이미 확정됨
    notes = confirm_order(db, session, order, state)
    _save(session, state)
    return response(db, session, order, state, notes=notes, override=state.get("override"))


def scan_coupon(db: Session, session: KioskSession, barcode: str) -> dict:
    """바코드 스캐너로 읽은 쿠폰 값 (POST /api/sessions/{id}/coupon)."""
    state = _state(session)
    order = cart_svc.open_order(db, session)
    if order.status != "pending_payment" or session.step not in (COUPON, PAYMENT):
        raise ApiError(409, "INVALID_STATE", "주문 확인을 마친 뒤 쿠폰을 쓸 수 있습니다", {"step": session.step})
    if order.coupon is not None:
        raise ApiError(409, "COUPON_ALREADY_APPLIED", "이미 쿠폰을 적용했습니다. 쿠폰은 주문 하나에 한 장만 쓸 수 있습니다")
    if any(p.status == "pending" for p in order.payments):
        raise ApiError(409, "INVALID_STATE", "결제가 진행 중입니다")
    session.step = COUPON
    notes, override = apply_coupon(db, session, order, state, barcode)
    state["override"] = override
    _save(session, state)
    return response(db, session, order, state, notes=notes, intent="COUPON", override=override)


def remove_coupon(db: Session, session: KioskSession) -> dict:
    state = _state(session)
    order = cart_svc.open_order(db, session)
    if order.status != "pending_payment" or any(p.status == "pending" for p in order.payments):
        raise ApiError(409, "INVALID_STATE", "지금은 쿠폰을 뺄 수 없습니다")
    order.coupon = None
    recalc(order, now_utc())
    session.step = COUPON
    state["awaiting"] = None
    _save(session, state)
    return response(db, session, order, state, notes=["쿠폰을 뺐어요."])
