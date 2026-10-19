"""손님 말 → 키오스크 표준 문장 (의도 파악 2번: 우리가 파인튜닝한 작은 LLM, nlu-gen-v1).

분류 모델(nlu_intent)이 못 고른 말, 특히 메뉴 이름이 들어간 말을 표준 문장으로 다시 쓴다.
예: (메뉴) "그 매운 닭 버거 두 개" → "맥스파이시 상하이 버거 2개 주세요"
Qwen2.5-1.5B-Instruct + LoRA 를 GGUF(Q4_K_M, 약 1GB)로 바꿔 llama.cpp 로 CPU 에서 돌린다. API 비용·인터넷 없음.
결과 문장은 백엔드가 다시 규칙·메뉴 DB 로 읽으므로, 모델이 없는 메뉴를 말해도 장바구니에 담기지 않는다.
학습: model/notebooks/nlu_gen_colab.ipynb · 모델 파일: model/scripts/fetch_nlu_model.sh (weights/nlu-gen-v1/)

환경변수
- NLU_GEN_MODEL: 모델 폴더 (기본 weights/nlu-gen-v1). 없으면 이 단계는 건너뜀
- NLU_GEN_THREADS: CPU 스레드 수 (기본: CPU 개수, 최대 8)
- NLU_GEN: 0 이면 끔
"""
import json
import logging
import os
import threading
import time

logger = logging.getLogger("uvicorn.error")

DEFAULT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "weights", "nlu-gen-v1")
MODEL_DIR = os.getenv("NLU_GEN_MODEL") or DEFAULT_DIR
THREADS = int(os.getenv("NLU_GEN_THREADS") or min(os.cpu_count() or 4, 8))
CONFIDENCE = 0.7  # 생성 모델은 확률을 따로 내지 않으므로 고정값 (백엔드 기준 0.5 이상)

_load_lock = threading.Lock()
_run_lock = threading.Lock()  # llama.cpp 모델 하나는 한 번에 한 문장만
_loaded = None  # (llm, meta)


def available() -> bool:
    return os.getenv("NLU_GEN", "1") != "0" and os.path.exists(os.path.join(MODEL_DIR, "model.gguf"))


def _load():
    global _loaded
    if _loaded is None:
        with _load_lock:
            if _loaded is None:
                from llama_cpp import Llama

                meta = json.load(open(os.path.join(MODEL_DIR, "meta.json"), encoding="utf-8"))
                t0 = time.time()
                llm = Llama(model_path=os.path.join(MODEL_DIR, "model.gguf"), n_ctx=512, n_threads=THREADS,
                            n_batch=256, verbose=False)
                _loaded = (llm, meta)
                logger.info("생성 모델 불러옴: %s (%.1f초, 스레드 %d)", meta.get("model_version"), time.time() - t0, THREADS)
    return _loaded


def preload_in_background() -> None:
    if available():
        threading.Thread(target=_safe_load, daemon=True).start()


def _safe_load() -> None:
    try:
        _load()
    except Exception:  # 불러오기 실패해도 서버는 돈다 (분류 모델·Claude 로 넘어감)
        logger.exception("생성 모델을 불러오지 못했습니다")


def is_ready() -> bool:
    return _loaded is not None


def model_version() -> str | None:
    return _loaded[1].get("model_version") if _loaded else None


def _prompt(meta: dict, text: str, step: str | None) -> str:
    # 학습 때(Qwen2.5 chat template)와 똑같은 모양
    user = meta["user_format"].format(step=meta["step_names"].get(step or "", step or ""), text=text)
    return (f"<|im_start|>system\n{meta['system']}<|im_end|>\n"
            f"<|im_start|>user\n{user}<|im_end|>\n<|im_start|>assistant\n")


def rewrite(text: str, step: str | None) -> dict:
    llm, meta = _load()
    t0 = time.time()
    with _run_lock:
        out = llm.create_completion(_prompt(meta, text, step), max_tokens=32, temperature=0.0,
                                    stop=["<|im_end|>", "\n"])
    answer = out["choices"][0]["text"].strip()
    if not answer or meta.get("unknown", "(모름)") in answer or answer == "모름":
        answer = ""
    return {"rewrite": answer, "confidence": CONFIDENCE if answer else 0.0,
            "model": meta.get("model_version", "nlu-gen"), "ms": round((time.time() - t0) * 1000)}
