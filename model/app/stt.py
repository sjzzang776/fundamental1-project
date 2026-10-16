"""음성 → 글자 (STT). Whisper small 을 faster-whisper(CTranslate2)로 실행한다.

환경변수
- WHISPER_MODEL: 모델 이름("small") 또는 변환된 모델 폴더 경로 (파인튜닝 후 교체용)
- WHISPER_DEVICE: cpu / cuda
- WHISPER_COMPUTE_TYPE: int8(CPU 권장) / float16(GPU)
- WHISPER_DOWNLOAD_DIR: 모델을 내려받아 둘 폴더 (개발 모드에서는 model/weights 에 저장됨)
"""

import logging
import math
import os
import threading
import time
from typing import BinaryIO

from faster_whisper import WhisperModel

logger = logging.getLogger("uvicorn.error")

MODEL_NAME = os.getenv("WHISPER_MODEL", "small")
DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
DOWNLOAD_DIR = os.getenv("WHISPER_DOWNLOAD_DIR", "/app/weights/whisper")
MAX_AUDIO_SECONDS = 15

_model: WhisperModel | None = None
_lock = threading.Lock()


class AudioTooLongError(Exception):
    pass


def get_model() -> WhisperModel:
    global _model
    with _lock:
        if _model is None:
            start = time.perf_counter()
            _model = WhisperModel(
                MODEL_NAME,
                device=DEVICE,
                compute_type=COMPUTE_TYPE,
                download_root=DOWNLOAD_DIR,
            )
            logger.info("Whisper '%s' 로드 완료 (%.1f초)", MODEL_NAME, time.perf_counter() - start)
    return _model


def preload_in_background() -> None:
    """서버 시작을 막지 않도록 모델을 백그라운드에서 미리 불러온다."""

    def _load():
        try:
            get_model()
        except Exception:
            logger.exception("Whisper 모델 미리 불러오기 실패 (첫 /stt 요청 때 다시 시도)")

    threading.Thread(target=_load, daemon=True).start()


def transcribe(audio: BinaryIO) -> dict:
    model = get_model()
    start = time.perf_counter()
    segments, info = model.transcribe(
        audio,
        language="ko",
        beam_size=5,
        vad_filter=True,  # 앞뒤 무음 제거
    )
    if info.duration > MAX_AUDIO_SECONDS + 0.5:
        raise AudioTooLongError(f"{info.duration:.1f}초")

    segments = list(segments)
    transcript = " ".join(s.text.strip() for s in segments).strip()
    # 구간별 평균 로그 확률을 0~1 사이 값으로 바꿔 신뢰도로 쓴다
    confidence = (
        math.exp(sum(s.avg_logprob for s in segments) / len(segments)) if segments else 0.0
    )
    logger.info(
        "STT %.1f초 음성 → %.2f초 처리: %s",
        info.duration,
        time.perf_counter() - start,
        transcript,
    )
    return {"transcript": transcript, "confidence": round(confidence, 2)}
