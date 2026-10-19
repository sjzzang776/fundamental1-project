"""장바구니. ERD처럼 status='cart' 인 orders 행이 장바구니입니다."""
from sqlalchemy.orm import Session

from ..db import now_utc
from ..errors import ApiError
from ..models import KioskSession, MenuItem, OptionGroup, OptionItem, Order, OrderItem, OrderItemOption
from .pricing import CouponProblem, recalc, unit_price

OPEN_STATUSES = ("cart", "pending_payment")
MAX_QUANTITY = 20


def open_order(db: Session, session: KioskSession) -> Order:
    """이 세션의 진행 중인 주문(장바구니)을 가져오고, 없으면 만든다."""
    for order in reversed(session.orders):
        if order.status in OPEN_STATUSES:
            return order
    order = Order(session=session, status="cart")
    db.add(order)
    db.flush()
    return order


def applicable_groups(menu: MenuItem, is_set: bool) -> list[OptionGroup]:
    want = "set" if is_set else "single"
    return [link.group for link in menu.option_links if link.applies_to in (want, "both")]


def default_option(group: OptionGroup) -> OptionItem:
    free = [o for o in group.items if o.extra_price == 0]
    return (free or group.items)[0]


def make_editable(order: Order) -> None:
    """결제 전 단계로 넘어간 주문을 다시 고칠 수 있게 장바구니로 되돌린다."""
    if order.status == "cart":
        return
    if order.status != "pending_payment":
        raise ApiError(409, "INVALID_STATE", "이미 결제된 주문은 바꿀 수 없습니다", {"status": order.status})
    for payment in order.payments:
        if payment.status == "pending":
            payment.status = "failed"
            payment.fail_reason = "CART_CHANGED"
    order.status = "cart"


def _resolve_options(db: Session, menu: MenuItem, is_set: bool, option_ids: list[int]) -> list[OptionItem]:
    groups = {g.id: g for g in applicable_groups(menu, is_set)}
    chosen: dict[int, list[OptionItem]] = {}
    for oid in option_ids:
        option = db.get(OptionItem, oid)
        if option is None or option.option_group_id not in groups:
            raise ApiError(400, "INVALID_OPTION", "이 메뉴에 고를 수 없는 옵션입니다", {"option_item_id": oid})
        chosen.setdefault(option.option_group_id, []).append(option)
    for gid, picked in chosen.items():
        if len(picked) > groups[gid].max_select:
            raise ApiError(400, "INVALID_OPTION", "옵션을 너무 많이 골랐습니다", {"group": groups[gid].name})
    missing = [g.name for g in groups.values() if g.is_required and g.id not in chosen]
    if missing:
        raise ApiError(400, "INVALID_OPTION", "꼭 골라야 하는 옵션이 빠졌습니다", {"missing_groups": missing})
    return [o for gid in sorted(chosen) for o in chosen[gid]]


def add_item(
    db: Session, order: Order, menu_id: int, quantity: int, is_set: bool, option_ids: list[int]
) -> tuple[OrderItem, CouponProblem | None]:
    menu = db.get(MenuItem, menu_id)
    if menu is None:
        raise ApiError(404, "MENU_NOT_FOUND", "없는 메뉴입니다", {"menu_id": menu_id})
    if not menu.is_available:
        raise ApiError(409, "MENU_SOLD_OUT", "품절된 메뉴입니다", {"menu_id": menu_id})
    if not 1 <= quantity <= MAX_QUANTITY:
        raise ApiError(400, "INVALID_QUANTITY", f"수량은 1~{MAX_QUANTITY}개만 고를 수 있습니다")
    if is_set and menu.set_price is None:
        raise ApiError(400, "INVALID_OPTION", "세트가 없는 메뉴입니다", {"menu_id": menu_id})
    make_editable(order)
    options = _resolve_options(db, menu, is_set, option_ids)

    # 같은 메뉴·같은 옵션이 이미 있으면 수량만 늘린다
    key = sorted(o.id for o in options)
    for item in order.items:
        if item.menu_item_id == menu_id and item.is_set == is_set and sorted(o.option_item_id for o in item.options) == key:
            if item.quantity + quantity > MAX_QUANTITY:
                raise ApiError(400, "INVALID_QUANTITY", f"수량은 1~{MAX_QUANTITY}개만 고를 수 있습니다")
            item.quantity += quantity
            return item, recalc(order, now_utc())

    price = unit_price(menu, is_set, sum(o.extra_price for o in options))
    item = OrderItem(menu=menu, is_set=is_set, quantity=quantity, unit_price=price, line_total=price * quantity)
    item.options = [OrderItemOption(option=o, extra_price=o.extra_price) for o in options]
    order.items.append(item)
    return item, recalc(order, now_utc())


def find_item(order: Order, item_id: int) -> OrderItem:
    for item in order.items:
        if item.id == item_id:
            return item
    raise ApiError(404, "CART_ITEM_NOT_FOUND", "장바구니에 없는 항목입니다", {"item_id": item_id})


def update_item(
    db: Session, order: Order, item: OrderItem, quantity: int | None = None, option_ids: list[int] | None = None
) -> CouponProblem | None:
    make_editable(order)
    if quantity is not None:
        if not 1 <= quantity <= MAX_QUANTITY:
            raise ApiError(400, "INVALID_QUANTITY", f"수량은 1~{MAX_QUANTITY}개만 고를 수 있습니다")
        item.quantity = quantity
    if option_ids is not None:
        # 보낸 옵션의 그룹만 바꾸고 나머지는 그대로 둔다. 예: 확인 화면 [사이드 바꾸기] → 맥너겟 id 하나만 보내면 됨
        by_group = {o.option.option_group_id: o.option_item_id for o in item.options}
        for oid in option_ids:
            option = db.get(OptionItem, oid)
            if option is None:
                raise ApiError(400, "INVALID_OPTION", "이 메뉴에 고를 수 없는 옵션입니다", {"option_item_id": oid})
            by_group[option.option_group_id] = oid
        options = _resolve_options(db, item.menu, item.is_set, list(by_group.values()))
        item.options = [OrderItemOption(option=o, extra_price=o.extra_price) for o in options]
        item.unit_price = unit_price(item.menu, item.is_set, sum(o.extra_price for o in options))
    return recalc(order, now_utc())


def remove_item(order: Order, item: OrderItem) -> CouponProblem | None:
    make_editable(order)
    order.items.remove(item)
    return recalc(order, now_utc())


def clear(order: Order) -> None:
    make_editable(order)
    order.items.clear()
    order.coupon = None
    recalc(order, now_utc())


# ---------- 화면·음성용 표현 ----------

def item_label(item: OrderItem) -> str:
    name = item.menu.name + (" 세트" if item.is_set else "")
    if item.options:
        name += "(" + ", ".join(o.option.name for o in item.options) + ")"
    return name


def count_word(n: int) -> str:
    return {1: "하나", 2: "둘", 3: "셋", 4: "넷", 5: "다섯"}.get(n, f"{n}개")


def won(amount: int) -> str:
    return f"{amount:,}원"


def cart_view(order: Order) -> dict:
    return {
        "order_id": order.id,
        "status": order.status,
        "dine_type": order.dine_type,
        "items": [
            {
                "item_id": i.id,
                "menu_id": i.menu_item_id,
                "menu_name": i.menu.name,
                "is_set": i.is_set,
                "options": [
                    {
                        "option_item_id": o.option_item_id,
                        "name": o.option.name,
                        "extra_price": o.extra_price,
                        "option_group_id": o.option.option_group_id,
                        "group": o.option.group.name,  # 확인 화면 "사이드: 후렌치 후라이 [바꾸기]" 용
                    }
                    for o in i.options
                ],
                "label": item_label(i),
                "quantity": i.quantity,
                "unit_price": i.unit_price,
                "line_total": i.line_total,
            }
            for i in order.items
        ],
        "subtotal": order.subtotal,
        "discount_amount": order.discount_amount,
        "coupon": {"barcode": order.coupon.barcode, "name": order.coupon.name} if order.coupon else None,
        "total_amount": order.total_amount,
    }
