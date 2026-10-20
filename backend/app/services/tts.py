"""안내 문장 → 사람 목소리 음성 (Google Cloud Text-to-Speech, Chirp 3 HD).

PM 결정 2026-10-19 (변경): 브라우저 기계음 대신 사람에 가까운 HD 목소리. 키가 없거나 실패하면 화면은 브라우저 목소리로 대신 읽는다.
- 안내를 문장 단위로 나눠 만들고(동시에), 하나의 WAV 로 이어 붙여 보낸다 → 화면은 한 번에 재생
  문장마다 앞뒤 무음(0.3~0.7초)이 붙어 나오므로 잘라 내고 문장 사이는 SENTENCE_GAP_S(0.2초)만 둔다 (2026-10-20 "공백에서 끊긴다")
- 한 번 만든 문장 음성은 메모리에 저장해 다시 쓴다 (고정 문장 "더 필요하신 건 있으세요?" 등은 바로 나감, 비용도 줄어듦)
- 서버가 켜질 때 자주 나오는 안내 문장을 미리 만들어 둔다 (HD 목소리는 문장당 0.6~1초 걸림)
- 쉼표는 그대로 읽힌다. 2026-10-19 에 쉼표를 빼 봤으나, 재 보니 쉼표를 빼면 오히려 "드시고 가세요 | 포장하세요?" 사이를
  매번 0.4초 쉬고, 쉼표가 있으면 대부분 쉬지 않고 더 짧게 읽었다 (2026-10-20 측정, 각 3번)

환경변수
- TTS_API_KEY: Google Cloud API 키 (Text-to-Speech 에만 쓰도록 제한). 없으면 /api/tts 는 503
- TTS_VOICE: 목소리 (기본 ko-KR-Chirp3-HD-Aoede, 여성). 예: ko-KR-Chirp3-HD-Charon (남성)
- TTS_RATE: 말 빠르기 (기본 1.1. PM 요청 2026-10-20: 10% 천천히(1.0) 해 봤으나 원래 속도가 나아 1.1 로 되돌림)
손님이 "천천히 말해 줘" / "빨리 말해 줘" / "크게 말해 줘" 라고 하면 화면이 speed 를 보내고 그만큼 바꾼다 (SPEEDS)
"""
import array
import base64
import io
import logging
import os
import re
import sys
import threading
import wave
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

import httpx

log = logging.getLogger("backend")

API_KEY = os.getenv("TTS_API_KEY", "")
VOICE = os.getenv("TTS_VOICE", "ko-KR-Chirp3-HD-Aoede")
RATE = float(os.getenv("TTS_RATE", "1.1"))
SPEEDS = {"normal": 1.0, "slower": 0.85, "faster": 1.15, "louder": 0.92}  # 크게: 조금 천천히 또박또박
URL = "https://texttospeech.googleapis.com/v1/text:synthesize"
CACHE_SIZE = 500
SAMPLE_RATE = 24000
SENTENCE_GAP_S = 0.2  # 이어 붙일 때 문장 사이 쉼
LEAD_KEEP_S = 0.04  # 잘라 낸 뒤 앞에 남길 무음 (첫소리가 갑자기 시작하지 않게)
TAIL_KEEP_S = 0.08

# 서버가 켜질 때 미리 만들어 둘 안내 문장 (dialog.py 의 고정 문장). 화면은 안내를 문장 단위로 나눠 받으므로 문장 하나씩
COMMON_PROMPTS = [
    "안녕하세요!", "드시고 가세요, 포장하세요?",
    "어떤 걸 드시고 싶으세요?", "고르기 어려우시면 추천해 드릴게요.",
    "더 필요하신 건 있으세요?", "다 고르셨으면 '주문할게요'라고 말씀해 주세요.",
    "음료는 뭐로 드릴까요?", "기본은 코카콜라예요.",
    "맞으세요?", "앱 쿠폰 있으세요?", "있으시면 휴대폰 바코드를 화면 아래 빛나는 곳에 대 주세요.",
    "휴대폰 바코드를 화면 아래 빛나는 곳에 대 주세요.", "카드를 화면 아래 빛나는 곳에 꽂아 주세요.",
    "다시 한번 말씀해 주세요.", "화면의 버튼을 눌러도 돼요.", "도움이 필요하세요?",
    "그 메뉴는 없어요.", "어떤 걸 바꿔 드릴까요?", "직원을 불렀어요.", "잠시만 기다려 주세요.",
    "결제가 안 됐어요.", "다시 해 볼까요, 직원을 불러 드릴까요?", "쿠폰 없이 결제할까요?",
]

_cache: OrderedDict[str, bytes] = OrderedDict()
_lock = threading.Lock()


class TtsUnavailable(Exception):
    pass


def available() -> bool:
    return bool(API_KEY)


_pool = ThreadPoolExecutor(max_workers=4)


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.?!])\s+", text or "") if s.strip()]


def speak_text(sentence: str) -> str:
    """읽힐 글자 (쉼표도 그대로. 위 설명 참고)."""
    return sentence.strip()


def trim_silence(pcm: bytes) -> bytes:
    """16비트 음성의 앞뒤 무음을 잘라 낸다 (소리가 가장 큰 곳의 3% 보다 작은 부분)."""
    samples = array.array("h", pcm)
    if sys.byteorder == "big":
        samples.byteswap()
    win = SAMPLE_RATE // 100  # 10ms
    levels = [max((abs(x) for x in samples[i:i + win]), default=0) for i in range(0, len(samples), win)]
    if not levels or max(levels) == 0:
        return pcm
    th = max(max(levels) * 0.03, 150)
    loud = [i for i, v in enumerate(levels) if v >= th]
    start = max(0, loud[0] * win - int(LEAD_KEEP_S * SAMPLE_RATE))
    end = min(len(samples), (loud[-1] + 1) * win + int(TAIL_KEEP_S * SAMPLE_RATE))
    return pcm[start * 2:end * 2]


def to_wav(pcm: bytes) -> bytes:
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm)
    return out.getvalue()


def synthesize(text: str, speed: str = "normal") -> bytes:
    """안내 전체 → WAV 하나 (문장별 음성을 동시에 만들고 앞뒤 무음을 잘라 0.2초 간격으로 이어 붙임)."""
    sentences = split_sentences(text) or [text.strip()]
    parts = list(_pool.map(lambda s: synthesize_sentence(s, speed), sentences))
    gap = bytes(2) * int(SENTENCE_GAP_S * SAMPLE_RATE)
    return to_wav(gap.join(parts))


def synthesize_sentence(text: str, speed: str = "normal") -> bytes:
    """문장 하나 → 앞뒤 무음을 잘라 낸 16비트 음성(PCM). 저장해 둔 게 있으면 바로 돌려준다."""
    text = text.strip()
    rate = round(RATE * SPEEDS.get(speed, 1.0), 2)
    key = f"{rate}|{text}"
    with _lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
    if not API_KEY:
        raise TtsUnavailable("TTS_API_KEY 가 없습니다")
    body = {
        "input": {"text": speak_text(text)},
        "voice": {"languageCode": "ko-KR", "name": VOICE},
        "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": SAMPLE_RATE, "speakingRate": rate},
    }
    try:
        r = httpx.post(URL, params={"key": API_KEY}, json=body, timeout=8)
        r.raise_for_status()
        raw = base64.b64decode(r.json()["audioContent"])
    except (httpx.HTTPError, KeyError, ValueError) as e:
        # 키 값이 로그에 남지 않게 주소(params)는 빼고 기록
        raise TtsUnavailable(f"음성 합성 실패: {type(e).__name__}") from e
    try:  # LINEAR16 은 WAV 머리말이 붙어 온다
        with wave.open(io.BytesIO(raw)) as w:
            pcm = w.readframes(w.getnframes())
    except (wave.Error, EOFError):
        pcm = raw
    audio = trim_silence(pcm)
    with _lock:
        _cache[key] = audio
        while len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)
    return audio


def prewarm_in_background() -> None:
    if not API_KEY:
        return

    def run():
        for text in COMMON_PROMPTS:
            try:
                synthesize_sentence(text)
            except TtsUnavailable as e:
                log.warning("안내 음성 미리 만들기 실패: %s", e)
                return
        log.info("안내 음성 %d개 미리 만듦 (%s)", len(COMMON_PROMPTS), VOICE)

    threading.Thread(target=run, daemon=True).start()
