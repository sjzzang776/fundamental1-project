from sqlalchemy.orm import Session

from ..errors import ApiError
from ..models import KioskSession
from ..services import dialog


def load_session(db: Session, session_id: int, allow_done: bool = False) -> KioskSession:
    session = db.get(KioskSession, session_id)
    if session is None:
        raise ApiError(404, "SESSION_NOT_FOUND", "없는 주문 세션입니다", {"session_id": session_id})
    # 화면 쪽 15초 안내와 별개로, 오래 반응이 없으면 서버가 세션을 끝낸다 (결제 단계는 3분, 그 밖은 5분)
    if session.ended_at is None and dialog.is_stale(session):
        dialog.expire_session(session, "timeout")
        db.commit()
    if session.ended_at is not None and not allow_done:
        raise ApiError(410, "SESSION_EXPIRED", "끝난 주문 세션입니다. 처음 화면으로 돌아가 주세요", {"end_reason": session.end_reason})
    return session
