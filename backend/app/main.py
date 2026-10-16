import os

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, text

MODEL_URL = os.getenv("MODEL_URL", "http://localhost:8001")
DATABASE_URL = os.getenv("DATABASE_URL")

app = FastAPI(title="Fundamental 1 Backend")
engine = create_engine(DATABASE_URL, pool_pre_ping=True) if DATABASE_URL else None


class PredictRequest(BaseModel):
    text: str


@app.get("/api/health")
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


@app.post("/api/predict")
async def predict(req: PredictRequest):
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(f"{MODEL_URL}/predict", json=req.model_dump())
            r.raise_for_status()
            return r.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"모델 서버 호출 실패: {e}")
