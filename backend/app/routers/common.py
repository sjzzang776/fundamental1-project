import os
from datetime import timedelta

from sqlalchemy.orm import Session

from ..db import aware, now_utc
from ..errors import ApiError
from ..models import KioskSession
from ..services import dialog

# 화면 쪽 15초 안내("도움이 필요하세요?")와 별개로, 이 시간 동안 아무 요청이 없으면 서버가 세션을 끝낸다
SESSION_IDLE_LIMIT_SEC = int(os.getenv("SESSION_IDLE_LIMIT_SEC", "300"))


def load_session(db: Session, session_id: int, allow_done: bool = False) -> KioskSession:
    session = db.get(KioskSession, session_id)
    if session is None:
        raise ApiError(404, "SESSION_NOT_FOUND", "없는 주문 세션입니다", {"session_id": session_id})
    if session.ended_at is None and session.step != dialog.PAYMENT:
        idle = now_utc() - aware(session.last_active_at)
        if idle > timedelta(seconds=SESSION_IDLE_LIMIT_SEC):
            for order in session.orders:
                if order.status in ("cart", "pending_payment"):
                    dialog.cancel_order(session, order)
            dialog.end_session(session, "timeout")
            db.commit()
    if session.ended_at is not None and not allow_done:
        raise ApiError(410, "SESSION_EXPIRED", "끝난 주문 세션입니다. 처음 화면으로 돌아가 주세요", {"end_reason": session.end_reason})
    return session
