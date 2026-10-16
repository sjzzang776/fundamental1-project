from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db, today_kst
from ..errors import ApiError
from ..models import Order, Payment
from ..services import cart as cart_svc
from ..services import dialog, payments

router = APIRouter(prefix="/api", tags=["주문·결제"])


class PaymentRequest(BaseModel):
    method: str = "card"


class PaymentConfirmRequest(BaseModel):
    """모의 PG: 카드 단말(또는 화면의 테스트 버튼)이 결제 결과를 알려준다."""
    payment_id: int
    amount: int
    success: bool = True
    pg_transaction_id: str | None = None
    fail_reason: str | None = Field(default=None, max_length=200)


def _order(db: Session, order_id: int) -> Order:
    order = db.get(Order, order_id)
    if order is None:
        raise ApiError(404, "ORDER_NOT_FOUND", "없는 주문입니다", {"order_id": order_id})
    return order


def order_view(order: Order) -> dict:
    return {
        **cart_svc.cart_view(order),
        "order_number": order.order_number,
        "order_date": order.order_date.isoformat(),
        "created_at": order.created_at.isoformat(),
        "paid_at": order.paid_at.isoformat() if order.paid_at else None,
        "ready_at": order.ready_at.isoformat() if order.ready_at else None,
    }


@router.get("/orders/{order_id}")
def get_order(order_id: int, db: Session = Depends(get_db)):
    return order_view(_order(db, order_id))


@router.post("/orders/{order_id}/cancel")
def cancel_order(order_id: int, db: Session = Depends(get_db)):
    order = _order(db, order_id)
    dialog.cancel_order(order.session, order)
    if order.session.ended_at is None:
        dialog.end_session(order.session, "cancelled")
    db.commit()
    return order_view(order)


@router.post("/orders/{order_id}/payments", status_code=201)
def request_payment(
    order_id: int,
    req: PaymentRequest | None = None,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
):
    """결제 요청. 같은 Idempotency-Key 로 다시 보내면 같은 결제를 돌려준다 (중복 결제 방지)."""
    if not idempotency_key:
        raise ApiError(400, "IDEMPOTENCY_KEY_REQUIRED", "Idempotency-Key 헤더가 필요합니다")
    method = (req or PaymentRequest()).method
    if method != "card":
        raise ApiError(400, "INVALID_INPUT", "지금은 카드 결제만 됩니다")
    payment = payments.request_payment(db, _order(db, order_id), idempotency_key, method)
    db.commit()
    return payments.payment_view(payment)


@router.post("/payments/confirm")
def confirm_payment(req: PaymentConfirmRequest, db: Session = Depends(get_db)):
    """결제 결과 처리. 금액을 서버 값과 다시 비교한 뒤 승인한다. 실패해도 200으로 다시 시도 안내를 돌려준다."""
    payment = db.get(Payment, req.payment_id)
    if payment is None:
        raise ApiError(404, "PAYMENT_NOT_FOUND", "없는 결제입니다", {"payment_id": req.payment_id})
    body = payments.confirm(db, payment, req.amount, req.success, req.pg_transaction_id, req.fail_reason)
    db.commit()
    return body


@router.get("/pickup-board")
def pickup_board(db: Session = Depends(get_db)):
    """호출 화면: 오늘 주문 중 준비 중인 번호와 음식이 나온 번호."""
    rows = db.scalars(
        select(Order).where(Order.order_date == today_kst(), Order.status.in_(("paid", "cooking", "ready"))).order_by(Order.order_number)
    ).all()
    return {
        "cooking": [o.order_number for o in rows if o.status in ("paid", "cooking")],
        "ready": [o.order_number for o in rows if o.status == "ready"],
    }
