import os

import httpx
from fastapi import APIRouter, Depends, File, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..errors import ApiError
from ..models import Kiosk, KioskSession, StaffCall
from ..services import cart as cart_svc
from ..services import dialog
from .common import load_session

router = APIRouter(prefix="/api", tags=["주문 세션·대화"])

MODEL_URL = os.getenv("MODEL_URL", "http://localhost:8001")
MAX_AUDIO_BYTES = 5 * 1024 * 1024


class StartRequest(BaseModel):
    kiosk_id: int = 1


class ChatRequest(BaseModel):
    text: str = Field(min_length=1, max_length=200)


class CartAddRequest(BaseModel):
    menu_id: int
    quantity: int = 1
    is_set: bool = False
    option_item_ids: list[int] = []


class CartUpdateRequest(BaseModel):
    quantity: int | None = None
    option_item_ids: list[int] | None = None


class CouponRequest(BaseModel):
    barcode: str = Field(min_length=1, max_length=50)


class StaffCallRequest(BaseModel):
    reason: str = "user_request"


@router.post("/sessions", status_code=201)
def start_session(req: StartRequest | None = None, db: Session = Depends(get_db)):
    req = req or StartRequest()
    if db.get(Kiosk, req.kiosk_id) is None:
        raise ApiError(404, "KIOSK_NOT_FOUND", "없는 키오스크입니다", {"kiosk_id": req.kiosk_id})
    # 같은 키오스크에서 끝나지 않은 이전 세션은 정리한다 (결제 중이면 그대로 둔다)
    for old in db.scalars(select(KioskSession).where(KioskSession.kiosk_id == req.kiosk_id, KioskSession.ended_at.is_(None))):
        if old.step == dialog.PAYMENT:
            continue
        for order in old.orders:
            if order.status in cart_svc.OPEN_STATUSES:
                dialog.cancel_order(old, order)
        dialog.end_session(old, "timeout")
    session = KioskSession(kiosk_id=req.kiosk_id, step=dialog.DINE_TYPE, dialog_state={})
    db.add(session)
    db.flush()
    body = dialog.start(db, session)
    db.commit()
    return body


@router.get("/sessions/{session_id}")
def get_session(session_id: int, db: Session = Depends(get_db)):
    session = load_session(db, session_id, allow_done=True)
    return dialog.current(db, session)


@router.delete("/sessions/{session_id}", status_code=204)
def end_session(session_id: int, reason: str = "cancelled", db: Session = Depends(get_db)):
    """처음으로 돌아가기. 화면에서 무응답(15초+15초)이면 reason=timeout 으로 호출한다."""
    if reason not in ("cancelled", "timeout"):
        raise ApiError(400, "INVALID_INPUT", "reason 은 cancelled 또는 timeout 입니다")
    session = load_session(db, session_id, allow_done=True)
    if session.ended_at is None:
        for order in session.orders:
            if order.status in cart_svc.OPEN_STATUSES:
                dialog.cancel_order(session, order)
        dialog.end_session(session, reason)
        db.commit()
    return Response(status_code=204)


@router.post("/sessions/{session_id}/chat")
def chat(session_id: int, req: ChatRequest, db: Session = Depends(get_db)):
    """손님이 한 말(또는 누른 버튼의 글자)을 처리한다."""
    session = load_session(db, session_id)
    body = dialog.handle(db, session, req.text)
    db.commit()
    return body


@router.post("/sessions/{session_id}/voice")
async def voice(session_id: int, audio: UploadFile = File(...), db: Session = Depends(get_db)):
    """녹음 파일 → 모델 서버 STT → chat 과 같은 처리."""
    session = load_session(db, session_id)
    data = await audio.read()
    if not data or len(data) > MAX_AUDIO_BYTES:
        raise ApiError(400, "INVALID_AUDIO", "녹음 파일이 비었거나 너무 큽니다 (최대 5MB)")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                f"{MODEL_URL}/stt", files={"audio": (audio.filename or "audio.webm", data, audio.content_type or "audio/webm")}
            )
            r.raise_for_status()
            transcript = r.json()["transcript"]
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise ApiError(502, "MODEL_UNAVAILABLE", "음성 인식을 할 수 없습니다. 화면의 버튼으로 주문해 주세요", {"reason": str(exc)[:200]})
    if not transcript.strip():
        transcript = ""
    body = dialog.handle(db, session, transcript, transcript=transcript)
    db.commit()
    return body


# ---------- 버튼으로 장바구니 바꾸기 ----------

@router.post("/sessions/{session_id}/cart/items")
def add_cart_item(session_id: int, req: CartAddRequest, db: Session = Depends(get_db)):
    session = load_session(db, session_id)
    order = cart_svc.open_order(db, session)
    item, problem = cart_svc.add_item(db, order, req.menu_id, req.quantity, req.is_set, req.option_item_ids)
    db.flush()
    notes = [f"{cart_svc.item_label(item)} 담았어요."]
    if problem:
        notes.append(dialog.coupon_dropped(problem))
    body = dialog.after_cart_change(db, session, order, notes)
    db.commit()
    return body


@router.patch("/sessions/{session_id}/cart/items/{item_id}")
def update_cart_item(session_id: int, item_id: int, req: CartUpdateRequest, db: Session = Depends(get_db)):
    session = load_session(db, session_id)
    order = cart_svc.open_order(db, session)
    item = cart_svc.find_item(order, item_id)
    problem = cart_svc.update_item(db, order, item, quantity=req.quantity, option_ids=req.option_item_ids)
    db.flush()
    notes = [f"{cart_svc.item_label(item)} {dialog.ro(cart_svc.count_word(item.quantity))} 바꿨어요."]
    if problem:
        notes.append(dialog.coupon_dropped(problem))
    body = dialog.after_cart_change(db, session, order, notes)
    db.commit()
    return body


@router.delete("/sessions/{session_id}/cart/items/{item_id}")
def remove_cart_item(session_id: int, item_id: int, db: Session = Depends(get_db)):
    session = load_session(db, session_id)
    order = cart_svc.open_order(db, session)
    item = cart_svc.find_item(order, item_id)
    label = cart_svc.item_label(item)
    problem = cart_svc.remove_item(order, item)
    db.flush()
    notes = [f"{dialog.josa(label, '을', '를')} 뺐어요."]
    if problem:
        notes.append(dialog.coupon_dropped(problem))
    body = dialog.after_cart_change(db, session, order, notes)
    db.commit()
    return body


# ---------- 주문 확정 · 쿠폰 · 직원 호출 ----------

@router.post("/sessions/{session_id}/orders")
def confirm_order(session_id: int, db: Session = Depends(get_db)):
    """주문 확인 화면에서 [맞아요]. 장바구니를 결제 대기 주문으로 확정한다."""
    session = load_session(db, session_id)
    body = dialog.confirm_by_button(db, session)
    db.commit()
    return body


@router.post("/sessions/{session_id}/coupon")
def scan_coupon(session_id: int, req: CouponRequest, db: Session = Depends(get_db)):
    """키오스크 바코드 스캐너로 읽은 쿠폰 값. 쓸 수 없는 쿠폰이어도 200으로 안내 문장을 돌려준다."""
    session = load_session(db, session_id)
    body = dialog.scan_coupon(db, session, req.barcode)
    db.commit()
    return body


@router.delete("/sessions/{session_id}/coupon")
def remove_coupon(session_id: int, db: Session = Depends(get_db)):
    session = load_session(db, session_id)
    body = dialog.remove_coupon(db, session)
    db.commit()
    return body


@router.post("/sessions/{session_id}/staff-call", status_code=202)
def staff_call(session_id: int, req: StaffCallRequest | None = None, db: Session = Depends(get_db)):
    session = load_session(db, session_id, allow_done=True)
    reason = (req or StaffCallRequest()).reason
    if reason not in ("user_request", "payment_failed", "barcode_failed"):
        raise ApiError(400, "INVALID_INPUT", "reason 은 user_request, payment_failed, barcode_failed 중 하나입니다")
    call = StaffCall(session=session, reason=reason)
    db.add(call)
    db.commit()
    return {"staff_call_id": call.id, "reply_text": "직원을 불렀어요. 잠시만 기다려 주세요."}
