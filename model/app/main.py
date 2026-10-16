from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Fundamental 1 Model")

MODEL_VERSION = "dummy-0.1"


class PredictRequest(BaseModel):
    text: str


@app.get("/health")
def health():
    return {"status": "ok", "model_version": MODEL_VERSION}


@app.post("/predict")
def predict(req: PredictRequest):
    # TODO(모델 구축): 실제 모델을 불러와 추론하도록 교체하세요.
    # 학습된 모델 파일은 model/weights/ 에 두고 여기서 불러옵니다.
    return {
        "input": req.text,
        "result": f"[임시 결과] '{req.text}' 를 받았습니다",
        "model_version": MODEL_VERSION,
    }
