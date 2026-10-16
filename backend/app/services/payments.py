"""결제. PG사가 아직 정해지지 않아 '모의 PG(mock)'로 동작합니다.

흐름: 결제 요청(POST /api/orders/{id}/payments) → 카드 단말/PG 결과 → 승인 처리(POST /api/payments/confirm)
실제 PG를 고르면 request_payment 의 응답과 confirm 의 확인 부분만 그 PG 방식으로 바꾸면 됩니다.
"""
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import now_utc, today_kst
from ..errors import ApiError
from ..models import Order, Payment
from . import cart as cart_svc
from . import dialog

PG_NAME = "mock"


def request_payment(db: Session, order: Order, idempotency_key: str, method: str) -> Payment:
    existing = db.scalar(select(Payment).where(Payment.idempotency_key == idempotency_key))
    if existing is not None:
        if existing.order_id != order.id:
            raise ApiError(409, "IDEMPOTENCY_KEY_REUSED", "다른 주문에 이미 쓴 Idempotency-Key 입니다")
        return existing
    if order.status != "pending_payment":
        raise ApiError(409, "INVALID_STATE", "주문 확인을 마친 주문만 결제할 수 있습니다", {"status": order.status})
    if order.session.step not in (dialog.COUPON, dialog.PAYMENT):
        raise ApiError(409, "INVALID_STATE", "결제 단계가 아닙니다", {"step": order.session.step})
    payment = Payment(order=order, method=method, amount=order.total_amount, status="pending", idempotency_key=idempotency_key)
    db.add(payment)
    order.session.step = dialog.PAYMENT
    state = dict(order.session.dialog_state or {})
    state["awaiting"] = None
    order.session.dialog_state = state
    db.flush()
    return payment


def payment_view(payment: Payment) -> dict:
    order = payment.order
    first = cart_svc.item_label(order.items[0]) if order.items else ""
    more = f" 외 {len(order.items) - 1}건" if len(order.items) > 1 else ""
    return {
        "payment_id": payment.id,
        "order_id": order.id,
        "amount": payment.amount,
        "method": payment.method,
        "status": payment.status,
        "pg": PG_NAME,
        "order_name": first + more,
    }


def assign_order_number(db: Session, order: Order) -> int:
    """오늘 날짜의 다음 주문번호 (매일 1번부터, 같은 날 겹치지 않음)."""
    today = today_kst()
    for _ in range(5):
        last = db.scalar(select(func.max(Order.order_number)).where(Order.order_date == today)) or 0
        try:
            with db.begin_nested():
                order.order_date = today
                order.order_number = last + 1
                db.flush()
            return order.order_number
        except IntegrityError:
            continue
    raise ApiError(500, "ORDER_NUMBER_FAILED", "주문번호를 만들지 못했습니다. 다시 시도해 주세요")


def _fail(payment: Payment, reason: str) -> None:
    payment.status = "failed"
    payment.fail_reason = reason
    session = payment.order.session
    state = dict(session.dialog_state or {})
    state["awaiting"] = "PAYMENT_RETRY"
    session.dialog_state = state
    session.step = dialog.PAYMENT


def confirm(db: Session, payment: Payment, amount: int, success: bool, pg_transaction_id: str | None,
            fail_reason: str | None) -> dict:
    order = payment.order
    session = order.session
    if payment.status == "pending":
        if not success:
            _fail(payment, fail_reason or "PG_DECLINED")
        elif amount != payment.amount or payment.amount != order.total_amount:
            _fail(payment, "AMOUNT_MISMATCH")
        elif order.status != "pending_payment":
            _fail(payment, "ORDER_NOT_PAYABLE")
        elif order.coupon is not None and order.coupon.used_at is not None:
            _fail(payment, "COUPON_ALREADY_USED")
        else:
            now = now_utc()
            payment.status = "approved"
            payment.approved_at = now
            payment.pg_transaction_id = pg_transaction_id or f"{PG_NAME}-{payment.id}"
            order.status = "paid"
            order.paid_at = now
            if order.coupon is not None:
                order.coupon.used_at = now
            assign_order_number(db, order)
            dialog.end_session(session, "completed")
    elif payment.status != "approved":
        raise ApiError(409, "INVALID_STATE", "이미 끝난 결제입니다", {"payment_status": payment.status})

    state = dict(session.dialog_state or {})
    text, choices = dialog.prompt(db, session, order, state)
    return {
        **payment_view(payment),
        "order_status": order.status,
        "order_number": order.order_number,
        "fail_reason": payment.fail_reason,
        "step": session.step,
        "reply_text": text,
        "choices": choices,
    }
