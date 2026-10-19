from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app import stt

MODEL_VERSION = stt.MODEL_VERSION


@asynccontextmanager
async def lifespan(app: FastAPI):
    stt.preload_in_background()
    yield


app = FastAPI(title="Fundamental 1 Model", lifespan=lifespan)


def error(status: int, code: str, message: str) -> JSONResponse:
    # API 명세의 공통 에러 형식
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


class PredictRequest(BaseModel):
    text: str


@app.get("/health")
def health():
    return {"status": "ok", "model_version": MODEL_VERSION, "stt_ready": stt.is_ready()}


@app.get("/ready")
def ready():
    """음성 인식 모델을 다 불러왔으면 200, 아직이면 503 (쿠버네티스 readinessProbe 용)."""
    if stt.is_ready():
        return {"ready": True, "model_version": MODEL_VERSION}
    return error(503, "MODEL_LOADING", "음성 인식 모델을 불러오는 중입니다")


@app.post("/stt")
async def speech_to_text(audio: UploadFile = File(...), hints: str | None = Form(None)):
    """음성 파일(wav/webm 등, 최대 15초)을 받아 글자로 바꾼다.

    hints: 잘 알아들어야 할 단어를 쉼표로 구분 (예: 지금 화면의 버튼 "코카콜라,코카콜라 제로,스프라이트").
    안 보내면 백엔드 메뉴 이름·옵션·별명 전체를 힌트로 쓴다.
    """
    hint_list = [h.strip() for h in hints.split(",") if h.strip()] if hints is not None else None
    try:
        await run_in_threadpool(stt.get_model)
    except Exception as e:
        return error(503, "MODEL_UNAVAILABLE", f"음성 인식 모델을 불러오지 못했습니다: {e}")
    try:
        return await run_in_threadpool(stt.transcribe, audio.file, hint_list)
    except stt.AudioTooLongError as e:
        return error(400, "AUDIO_TOO_LONG", f"음성은 {stt.MAX_AUDIO_SECONDS}초 이내여야 합니다 (받은 길이: {e})")
    except Exception as e:
        return error(400, "INVALID_AUDIO", f"음성 파일을 읽을 수 없습니다: {e}")


@app.post("/predict")
def predict(req: PredictRequest):
    # (임시) 백엔드 연결 테스트용. 백엔드가 /chat 으로 바꾸면 지운다.
    return {
        "input": req.text,
        "result": f"[임시 결과] '{req.text}' 를 받았습니다",
        "model_version": MODEL_VERSION,
    }
