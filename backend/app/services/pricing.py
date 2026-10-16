"""금액 계산과 쿠폰 확인. 금액은 항상 서버가 계산합니다 (ERD 4. 규칙)."""
from datetime import datetime

from ..db import aware
from ..models import Coupon, MenuItem, Order


class CouponProblem(Exception):
    """쿠폰을 쓸 수 없는 이유. dialog가 손님에게 쉬운 말로 안내한다."""

    def __init__(self, code: str, coupon: Coupon | None = None, extra: dict | None = None):
        self.code = code
        self.coupon = coupon
        self.extra = extra or {}


def unit_price(menu: MenuItem, is_set: bool, option_extra: int) -> int:
    base = menu.set_price if is_set else menu.price
    return base + option_extra


def coupon_discount(coupon: Coupon, order: Order, now: datetime) -> int:
    """쿠폰 할인 금액. 쓸 수 없으면 CouponProblem."""
    if coupon.used_at is not None:
        raise CouponProblem("COUPON_ALREADY_USED", coupon)
    if now < aware(coupon.valid_from):
        raise CouponProblem("COUPON_NOT_STARTED", coupon)
    if now > aware(coupon.valid_until):
        raise CouponProblem("COUPON_EXPIRED", coupon)

    # 쿠폰 메뉴가 없는지 먼저 본다: 기획서 5-2 "해당 메뉴가 없으면 '쿠폰 메뉴를 담아 드릴까요?'"
    if coupon.target_menu_item_id is not None:
        targets = [i for i in order.items if i.menu_item_id == coupon.target_menu_item_id]
        if coupon.target_set_only:
            targets = [i for i in targets if i.is_set]
        if coupon.discount_type == "free_item":
            targets = [i for i in targets if not i.is_set]
        if not targets:
            raise CouponProblem("COUPON_MENU_MISSING", coupon)

    subtotal = sum(i.line_total for i in order.items)
    if subtotal < coupon.min_order_amount:
        raise CouponProblem("COUPON_MIN_AMOUNT", coupon, {"min_order_amount": coupon.min_order_amount})

    if coupon.discount_type == "fixed":
        discount = coupon.discount_value
    elif coupon.discount_type == "percent":
        discount = subtotal * coupon.discount_value // 100 // 10 * 10  # 10원 단위 버림
    elif coupon.discount_type == "free_item":
        discount = min(i.unit_price for i in targets)
    else:
        raise CouponProblem("COUPON_NOT_APPLICABLE", coupon)
    return min(discount, subtotal)


def recalc(order: Order, now: datetime) -> CouponProblem | None:
    """합계를 다시 계산한다. 장바구니가 바뀌어 쿠폰 조건이 깨지면 쿠폰을 빼고 그 이유를 돌려준다."""
    for item in order.items:
        item.line_total = item.unit_price * item.quantity
    order.subtotal = sum(i.line_total for i in order.items)
    problem = None
    order.discount_amount = 0
    if order.coupon is not None:
        try:
            order.discount_amount = coupon_discount(order.coupon, order, now)
        except CouponProblem as exc:
            problem = exc
            order.coupon = None
    order.total_amount = order.subtotal - order.discount_amount
    return problem
