import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

DATABASE_URL = os.getenv("DATABASE_URL")

# 한국 시간 (서머타임이 없어서 고정 +9시간)
KST = timezone(timedelta(hours=9))


class Base(DeclarativeBase):
    pass


def _make_engine(url):
    if not url:
        return None
    if url.startswith("sqlite"):
        # 테스트용 메모리 DB: 모든 연결이 같은 DB를 보도록 한다
        return create_engine(url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    return create_engine(url, pool_pre_ping=True)


engine = _make_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def today_kst():
    return now_utc().astimezone(KST).date()


def aware(dt: datetime | None) -> datetime | None:
    """SQLite는 시간대 정보를 버리므로 비교 전에 UTC로 맞춘다."""
    if dt is None or dt.tzinfo is not None:
        return dt
    return dt.replace(tzinfo=timezone.utc)
