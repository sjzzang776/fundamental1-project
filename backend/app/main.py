import logging
import os
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from .db import Base, SessionLocal, engine
from .errors import ApiError, register_error_handlers
from .routers import kitchen, menus, orders, sessions
from .seed import seed
from .services import tts as tts_svc

MODEL_URL = os.getenv("MODEL_URL", "http://localhost:8001")
log = logging.getLogger("backend")


def init_db(retries: int = 10) -> None:
    """테이블을 만들고(없을 때만) 기본 메뉴 데이터를 넣는다."""
    if engine is None:
        return
    for attempt in range(retries):
        try:
            Base.metadata.create_all(engine)
            with SessionLocal() as db:
                seed(db)
            return
        except OperationalError:
            log.warning("DB 연결 대기 중... (%s/%s)", attempt + 1, retries)
            time.sleep(2)
    raise RuntimeError("DB에 연결하지 못했습니다")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    tts_svc.prewarm_in_background()
    yield


app = FastAPI(title="Fundamental 1 Backend", lifespan=lifespan)
register_error_handlers(app)
app.include_router(menus.router)
app.include_router(sessions.router)
app.include_router(orders.router)
app.include_router(kitchen.router)


class PredictRequest(BaseModel):
    text: str


class TtsRequest(BaseModel):
    text: str = Field(min_length=1, max_length=300)


@app.get("/api/health", tags=["공통"])
def health():
    db_ok = False
    if engine is not None:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            db_ok = True
        except Exception:
            db_ok = False
    return {"status": "ok", "db": db_ok}


@app.post("/api/predict", tags=["공통"])
async def predict(req: PredictRequest):
    """(임시) 모델 서버 연결 확인용. GitHub CI가 이 주소를 확인한다."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(f"{MODEL_URL}/predict", json=req.model_dump())
            r.raise_for_status()
            return r.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"모델 서버 호출 실패: {e}")


@app.post("/api/tts", tags=["공통"])
async def tts(req: TtsRequest):
    """안내 문장 → 사람 목소리 음성 MP3 (Google Cloud TTS, Chirp 3 HD). services/tts.py 참고.

    키가 없거나 실패하면 503 → 화면은 브라우저 목소리로 대신 읽는다.
    """
    try:
        audio = await run_in_threadpool(tts_svc.synthesize, req.text)
    except tts_svc.TtsUnavailable as e:
        raise ApiError(503, "TTS_UNAVAILABLE", "음성 안내를 만들 수 없습니다. 브라우저 목소리로 읽어 주세요", {"reason": str(e)})
    return Response(content=audio, media_type="audio/mpeg", headers={"Cache-Control": "public, max-age=86400"})
