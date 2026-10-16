import os

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db, now_utc, today_kst
from ..errors import ApiError
from ..models import Order, StaffCall
from ..services import cart as cart_svc

# 비어 있으면 확인하지 않는다 (로컬 개발용). 매장에 둘 때는 .env 에 KITCHEN_TOKEN 을 넣는다.
KITCHEN_TOKEN = os.getenv("KITCHEN_TOKEN", "")


def kitchen_auth(x_kitchen_token: str | None = Header(default=None)):
    if KITCHEN_TOKEN and x_kitchen_token != KITCHEN_TOKEN:
        raise ApiError(401, "UNAUTHORIZED", "주방 화면 토큰이 맞지 않습니다")


router = APIRouter(prefix="/api", tags=["주방"], dependencies=[Depends(kitchen_auth)])

# 주방 상태 변경 규칙 (ERD 3. 상태 값). MVP는 [완료] 버튼만 써서 paid → ready 로 바로 넘어갈 수 있다.
NEXT_STATUS = {"paid": {"cooking", "ready"}, "cooking": {"ready"}, "ready": {"picked_up"}}


class KitchenUpdate(BaseModel):
    status: str


class StaffCallUpdate(BaseModel):
    resolved: bool = True


def _kitchen_order(o: Order) -> dict:
    return {
        "order_id": o.id,
        "order_number": o.order_number,
        "status": o.status,
        "dine_type": o.dine_type,
        "items": [{"label": cart_svc.item_label(i), "quantity": i.quantity} for i in o.items],
        "paid_at": o.paid_at.isoformat() if o.paid_at else None,
    }


@router.get("/kitchen/orders")
def kitchen_orders(status: str = "paid,cooking,ready", db: Session = Depends(get_db)):
    wanted = [s.strip() for s in status.split(",") if s.strip()]
    rows = db.scalars(
        select(Order).where(Order.order_date == today_kst(), Order.status.in_(wanted)).order_by(Order.order_number)
    ).all()
    return [_kitchen_order(o) for o in rows]


@router.patch("/kitchen/orders/{order_id}")
def update_kitchen_order(order_id: int, req: KitchenUpdate, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if order is None:
        raise ApiError(404, "ORDER_NOT_FOUND", "없는 주문입니다", {"order_id": order_id})
    if req.status not in NEXT_STATUS.get(order.status, set()):
        raise ApiError(409, "INVALID_STATE", "지금 상태에서 바꿀 수 없는 상태입니다", {"from": order.status, "to": req.status})
    order.status = req.status
    if req.status == "ready":
        order.ready_at = now_utc()
    db.commit()
    return _kitchen_order(order)


@router.get("/staff-calls")
def staff_calls(resolved: bool = False, db: Session = Depends(get_db)):
    query = select(StaffCall).order_by(StaffCall.id.desc())
    query = query.where(StaffCall.resolved_at.is_not(None) if resolved else StaffCall.resolved_at.is_(None))
    return [
        {
            "staff_call_id": c.id,
            "session_id": c.session_id,
            "kiosk_id": c.session.kiosk_id,
            "step": c.session.step,
            "reason": c.reason,
            "created_at": c.created_at.isoformat(),
            "resolved_at": c.resolved_at.isoformat() if c.resolved_at else None,
        }
        for c in db.scalars(query)
    ]


@router.patch("/staff-calls/{call_id}")
def resolve_staff_call(call_id: int, req: StaffCallUpdate, db: Session = Depends(get_db)):
    call = db.get(StaffCall, call_id)
    if call is None:
        raise ApiError(404, "STAFF_CALL_NOT_FOUND", "없는 직원 호출입니다", {"staff_call_id": call_id})
    call.resolved_at = now_utc() if req.resolved else None
    db.commit()
    return {"staff_call_id": call.id, "resolved_at": call.resolved_at.isoformat() if call.resolved_at else None}
