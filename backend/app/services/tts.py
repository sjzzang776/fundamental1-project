"""안내 문장 → 사람 목소리 음성 (Google Cloud Text-to-Speech, Chirp 3 HD).

PM 결정 2026-10-19 (변경): 브라우저 기계음 대신 사람에 가까운 HD 목소리. 키가 없거나 실패하면 화면은 브라우저 목소리로 대신 읽는다.
- 한 번 만든 음성은 메모리에 저장해 다시 쓴다 (안내 문장은 반복이 많아 대부분 바로 나감, 비용도 줄어듦)
- 서버가 켜질 때 자주 나오는 안내 문장을 미리 만들어 둔다 (HD 목소리는 문장당 1~2초 걸림)

환경변수
- TTS_API_KEY: Google Cloud API 키 (Text-to-Speech 에만 쓰도록 제한). 없으면 /api/tts 는 503
- TTS_VOICE: 목소리 (기본 ko-KR-Chirp3-HD-Aoede, 여성). 예: ko-KR-Chirp3-HD-Charon (남성)
- TTS_RATE: 말 빠르기 (기본 0.95, 어르신이 듣기 편하게 조금 천천히)
"""
import base64
import logging
import os
import threading
from collections import OrderedDict

import httpx

log = logging.getLogger("backend")

API_KEY = os.getenv("TTS_API_KEY", "")
VOICE = os.getenv("TTS_VOICE", "ko-KR-Chirp3-HD-Aoede")
RATE = float(os.getenv("TTS_RATE", "0.95"))
URL = "https://texttospeech.googleapis.com/v1/text:synthesize"
CACHE_SIZE = 500

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


def synthesize(text: str) -> bytes:
    """MP3 바이트. 저장해 둔 게 있으면 바로 돌려준다."""
    text = text.strip()
    with _lock:
        if text in _cache:
            _cache.move_to_end(text)
            return _cache[text]
    if not API_KEY:
        raise TtsUnavailable("TTS_API_KEY 가 없습니다")
    body = {
        "input": {"text": text},
        "voice": {"languageCode": "ko-KR", "name": VOICE},
        "audioConfig": {"audioEncoding": "MP3", "speakingRate": RATE},
    }
    try:
        r = httpx.post(URL, params={"key": API_KEY}, json=body, timeout=8)
        r.raise_for_status()
        audio = base64.b64decode(r.json()["audioContent"])
    except (httpx.HTTPError, KeyError, ValueError) as e:
        # 키 값이 로그에 남지 않게 주소(params)는 빼고 기록
        raise TtsUnavailable(f"음성 합성 실패: {type(e).__name__}") from e
    with _lock:
        _cache[text] = audio
        while len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)
    return audio


def prewarm_in_background() -> None:
    if not API_KEY:
        return

    def run():
        for text in COMMON_PROMPTS:
            try:
                synthesize(text)
            except TtsUnavailable as e:
                log.warning("안내 음성 미리 만들기 실패: %s", e)
                return
        log.info("안내 음성 %d개 미리 만듦 (%s)", len(COMMON_PROMPTS), VOICE)

    threading.Thread(target=run, daemon=True).start()
