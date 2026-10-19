import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app import nlu_gen, nlu_intent, nlu_llm, stt

MODEL_VERSION = stt.MODEL_VERSION
logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    stt.preload_in_background()
    nlu_gen.preload_in_background()
    yield


app = FastAPI(title="Fundamental 1 Model", lifespan=lifespan)


def error(status: int, code: str, message: str) -> JSONResponse:
    # API 명세의 공통 에러 형식
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


class PredictRequest(BaseModel):
    text: str


class NluRequest(BaseModel):
    text: str
    step: str | None = None
    cart: list[str] = []
    history: list = []
    menus: list[str] = []
    options: list[str] = []


@app.get("/health")
def health():
    return {"status": "ok", "model_version": MODEL_VERSION, "stt_ready": stt.is_ready(), "nlu_intent": nlu_intent.available(), "nlu_gen": nlu_gen.is_ready(), "nlu_llm": nlu_llm.available()}


@app.get("/ready")
def ready():
    """음성 인식 모델을 다 불러왔으면 200, 아직이면 503 (쿠버네티스 readinessProbe 용)."""
    if stt.is_ready():
        return {"ready": True, "model_version": MODEL_VERSION}
    return error(503, "MODEL_LOADING", "음성 인식 모델을 불러오는 중입니다")


# 분류 모델은 메뉴 문장으로 학습하지 않아서, 메뉴가 섞인 말("감자는 빼 줘")에도 이 답을 고를 때가 있다.
# 메뉴와 헷갈리기 쉽거나 주문을 지우는 답이므로, 생성 모델이 있으면 한 번 더 물어 생성 모델 답을 쓴다.
CHECK_WITH_GEN = {"세트로 주세요", "단품으로 주세요", "라지로 주세요", "미디엄으로 주세요", "하나 더 주세요", "취소", "처음으로"}


def _understand(req: NluRequest) -> dict:
    # 1) 작은 분류 모델 (빠르고 공짜): 표준 문장 18개 중 하나로 확신하면 바로 답한다
    tried = nlu_intent.available()
    picked = None
    if tried:
        picked = nlu_intent.classify(req.text, req.step)
        if picked["rewrite"] and not (picked["rewrite"] in CHECK_WITH_GEN and nlu_gen.available()):
            return picked
    # 2) 우리가 파인튜닝한 작은 LLM (있으면): 메뉴 이름이 들어간 말까지 다시 쓴다 (CPU, 공짜)
    if nlu_gen.available():
        tried = True
        try:
            result = nlu_gen.rewrite(req.text, req.step)
            if result["rewrite"]:
                return result
        except Exception:
            logger.exception("생성 모델 실패")
    if picked and picked["rewrite"]:  # 생성 모델이 모른다고 하면 분류 모델 답을 쓴다
        return picked
    # 3) Claude (API 키가 있을 때만): 위 둘이 못 한 말
    if nlu_llm.available():
        try:
            return nlu_llm.rewrite(req.text, req.step, req.menus, req.options, req.cart, req.history)
        except nlu_llm.NluUnavailable:
            if not tried:
                raise
    if tried:  # 우리 모델은 있으니 503 대신 "모름" (백엔드가 1분 동안 /nlu 를 건너뛰지 않게)
        return {"rewrite": "", "confidence": 0.0, "model": nlu_gen.model_version() or nlu_intent.model_version()}
    raise nlu_llm.NluUnavailable("의도 파악 모델도 API 키도 없습니다")


@app.post("/nlu")
async def nlu(req: NluRequest):
    """백엔드 규칙이 못 알아들은 손님 말을 키오스크가 아는 표준 문장으로 바꾼다 (C안).

    순서: 분류 모델(nlu-intent-v1) → 생성 모델(nlu-gen-v1) → Claude(ANTHROPIC_API_KEY 있으면). 없는 것은 건너뜀.
    응답: {"rewrite": "포장", "confidence": 0.9, "model": "..."}. 둘 다 없으면 503 → 백엔드는 규칙만 쓴다.
    """
    try:
        return await run_in_threadpool(_understand, req)
    except nlu_llm.NluUnavailable as e:
        return error(503, "NLU_UNAVAILABLE", str(e))


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
