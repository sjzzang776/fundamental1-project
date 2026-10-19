"""음성 → 글자 (STT). Whisper small 을 faster-whisper(CTranslate2)로 실행한다.

환경변수
- WHISPER_MODEL: 모델 이름("small") 또는 변환된 모델 폴더 경로 (파인튜닝 후 교체용)
- WHISPER_DEVICE: cpu / cuda
- WHISPER_COMPUTE_TYPE: int8(CPU 권장) / float16(GPU)
- WHISPER_DOWNLOAD_DIR: 모델을 내려받아 둘 폴더 (개발 모드에서는 model/weights 에 저장됨)
- BACKEND_URL: 메뉴 이름 힌트를 가져올 백엔드 주소
- STT_MENU_HINTS: 1(기본) = 요청에 hints 가 없으면 메뉴 이름을 힌트로 씀 / 0 = 끔 (힌트는 처리 시간을 약 0.5초 늘림)
"""

import logging
import math
import os
import re
import threading
import time
from typing import BinaryIO

import httpx
from faster_whisper import WhisperModel

logger = logging.getLogger("uvicorn.error")

MODEL_NAME = os.getenv("WHISPER_MODEL", "small")
DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
DOWNLOAD_DIR = os.getenv("WHISPER_DOWNLOAD_DIR", "/app/weights/whisper")
MAX_AUDIO_SECONDS = 15
BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")
HINTS_TTL_SECONDS = 300
MENU_HINTS_ON = os.getenv("STT_MENU_HINTS", "1") != "0"

_model: WhisperModel | None = None
_lock = threading.Lock()
_hints: list[str] = []
_hints_at = 0.0


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


def compact_hints(official: list[str], aliases: list[str]) -> list[str]:
    """힌트는 Whisper 가 약 220토큰까지만 쓰므로 줄인다.
    정식 이름·옵션은 모두 남기고 "코카콜라 (M)" → "코카콜라" 처럼 괄호와 중복만 뺀다.
    별명은 정식 이름 안에 이미 들어 있는 것("콜라", "제로", "상하이")만 뺀다."""
    strip = lambda w: re.sub(r"\s*\([^)]*\)", "", w).strip()
    official = [w for w in dict.fromkeys(map(strip, official)) if w]
    extra = [a for a in dict.fromkeys(map(strip, aliases)) if a and not any(a in o for o in official)]
    return official + extra


def menu_hints() -> list[str]:
    """백엔드 메뉴 이름·옵션·별명을 힌트 단어로 쓴다. 5분 동안 저장해 두고, 백엔드가 안 되면 저장해 둔 것을 쓴다."""
    global _hints, _hints_at
    if _hints and time.monotonic() - _hints_at < HINTS_TTL_SECONDS:
        return _hints
    try:
        with httpx.Client(base_url=BACKEND_URL, timeout=3) as client:
            names, options, aliases = [], [], []
            for m in client.get("/api/menus").raise_for_status().json():
                names.append(m["name"])
                detail = client.get(f"/api/menus/{m['id']}").raise_for_status().json()
                aliases += detail.get("aliases", [])
                options += [o["name"] for g in detail.get("option_groups", []) for o in g["items"]]
        _hints = compact_hints(names + options, aliases)
        _hints_at = time.monotonic()
        logger.info("메뉴 힌트 %d개 갱신", len(_hints))
    except (httpx.HTTPError, ValueError, KeyError) as e:
        logger.warning("메뉴 힌트를 가져오지 못했습니다 (%s). 이전 힌트 %d개 사용", e, len(_hints))
        _hints_at = time.monotonic() - HINTS_TTL_SECONDS + 30  # 30초 뒤 다시 시도
    return _hints


def transcribe(audio: BinaryIO, hints: list[str] | None = None) -> dict:
    """hints 를 주면 그 단어를, 안 주면 백엔드 메뉴 이름을 힌트로 쓴다. 빈 목록이면 힌트 없이 인식."""
    model = get_model()
    if hints is None:
        hints = menu_hints() if MENU_HINTS_ON else []
    start = time.perf_counter()
    segments, info = model.transcribe(
        audio,
        language="ko",
        beam_size=5,
        vad_filter=True,  # 앞뒤 무음 제거
        hotwords=", ".join(hints) if hints else None,
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
