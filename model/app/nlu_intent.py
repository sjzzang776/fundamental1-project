"""손님 말 → 키오스크 표준 문장 (의도 파악 1번: 작은 분류 모델, nlu-intent-v1).

백엔드 규칙이 못 알아들은 말을 표준 문장 18개 중 하나로 고른다 (예: (식사 장소) "봉투에 담아 줘" → "포장").
CPU 에서 문장당 수십 ms, API 비용·인터넷 없음. 확신이 기준값보다 낮거나 "모름"이면 빈 문자열.
학습: model/notebooks/nlu_intent_colab.ipynb · 데이터: model/scripts/make_nlu_data.py
모델 파일: model/scripts/fetch_nlu_model.sh 로 GitHub Release 에서 받음 (weights/nlu-intent-v1/)

환경변수
- NLU_INTENT_MODEL: 모델 폴더 (기본 weights/nlu-intent-v1). 없으면 이 단계는 건너뜀
- NLU_INTENT_THRESHOLD: 기준값 (기본: 학습할 때 정한 meta.json 의 threshold)
"""
import json
import logging
import os
import threading

import numpy as np

logger = logging.getLogger("uvicorn.error")

DEFAULT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "weights", "nlu-intent-v1")
MODEL_DIR = os.getenv("NLU_INTENT_MODEL") or DEFAULT_DIR

_lock = threading.Lock()
_loaded = None  # (session, tokenizer, meta)


def available() -> bool:
    return os.path.exists(os.path.join(MODEL_DIR, "model.onnx"))


def _load():
    global _loaded
    if _loaded is None:
        with _lock:
            if _loaded is None:
                import onnxruntime as ort
                from tokenizers import Tokenizer

                meta = json.load(open(os.path.join(MODEL_DIR, "meta.json"), encoding="utf-8"))
                tok = Tokenizer.from_file(os.path.join(MODEL_DIR, "tokenizer.json"))
                tok.no_padding()
                tok.enable_truncation(meta.get("max_len", 64))
                opts = ort.SessionOptions()
                opts.intra_op_num_threads = 2
                sess = ort.InferenceSession(os.path.join(MODEL_DIR, "model.onnx"), opts, providers=["CPUExecutionProvider"])
                _loaded = (sess, tok, meta)
                logger.info("의도 파악 모델 불러옴: %s", meta.get("model_version"))
    return _loaded


def model_version() -> str | None:
    return _load()[2].get("model_version") if available() else None


def classify(text: str, step: str | None) -> dict:
    sess, tok, meta = _load()
    step_name = meta["step_names"].get(step or "", step or "")
    enc = tok.encode(meta["input_format"].format(step=step_name, text=text))
    feed = {
        "input_ids": np.array([enc.ids], dtype=np.int64),
        "attention_mask": np.array([enc.attention_mask], dtype=np.int64),
    }
    logits = sess.run(None, feed)[0][0]
    probs = np.exp(logits - logits.max())
    probs /= probs.sum()
    i = int(probs.argmax())
    label, conf = meta["labels"][i], float(probs[i])
    threshold = float(os.getenv("NLU_INTENT_THRESHOLD") or meta.get("threshold", 0.8))
    rewrite = label if label != meta["none_label"] and conf >= threshold else ""
    return {"rewrite": rewrite, "confidence": round(conf if rewrite else 0.0, 3), "label": label,
            "model": meta.get("model_version", "nlu-intent")}
