"""안내 음성 /api/tts: 사람 목소리(Google TTS)를 만들고 저장해 다시 쓴다. 실제 Google 대신 가짜 응답으로 시험한다."""
import array
import base64
import io
import wave

import httpx
import pytest

from app.services import tts


@pytest.fixture()
def fake_google(monkeypatch):
    calls = []

    def post(url, params=None, json=None, timeout=None):
        calls.append(json)
        audio = base64.b64encode(fake_wav(LEAD_S, SPEECH_S, TAIL_S)).decode()
        return httpx.Response(200, json={"audioContent": audio}, request=httpx.Request("POST", url))

    monkeypatch.setattr(tts, "API_KEY", "test-key")
    monkeypatch.setattr(tts.httpx, "post", post)
    monkeypatch.setattr(tts, "_cache", type(tts._cache)())
    return calls


SR = tts.SAMPLE_RATE
LEAD_S, SPEECH_S, TAIL_S = 0.5, 0.3, 0.3  # Google 이 주는 음성처럼 앞뒤에 무음이 붙은 가짜 음성


def fake_wav(lead, speech, tail):
    """무음 lead 초 + 소리 speech 초 + 무음 tail 초 (LINEAR16 WAV)."""
    pcm = array.array("h", [0] * int(lead * SR) + [8000, -8000] * int(speech * SR / 2) + [0] * int(tail * SR))
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return out.getvalue()


def seconds(wav_bytes):
    with wave.open(io.BytesIO(wav_bytes)) as w:
        return w.getnframes() / w.getframerate()


def test_키가_없으면_503_화면은_브라우저_목소리로(client, monkeypatch):
    monkeypatch.setattr(tts, "API_KEY", "")
    r = client.post("/api/tts", json={"text": "안녕하세요"})
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "TTS_UNAVAILABLE"


def test_사람_목소리_WAV를_돌려주고_같은_문장은_다시_만들지_않는다(client, fake_google):
    for _ in range(3):
        r = client.post("/api/tts", json={"text": "드시고 가세요, 포장하세요?"})
        assert r.status_code == 200
        assert r.headers["content-type"] == "audio/wav"
    assert len(fake_google) == 1  # 두 번째부터는 저장해 둔 음성
    assert fake_google[0]["voice"]["name"] == tts.VOICE
    assert fake_google[0]["input"]["text"] == "드시고 가세요, 포장하세요?"  # 쉼표는 그대로 (빼면 오히려 쉼)
    assert fake_google[0]["audioConfig"]["speakingRate"] == 1.1  # 기본 빠르기


def test_문장_앞뒤_무음을_잘라_낸다(client, fake_google):
    r = client.post("/api/tts", json={"text": "안녕하세요!"})
    expected = SPEECH_S + tts.LEAD_KEEP_S + tts.TAIL_KEEP_S
    assert abs(seconds(r.content) - expected) < 0.03  # 원래 1.1초 → 약 0.42초


def test_문장_안의_긴_쉼은_줄이고_짧은_쉼은_그대로(monkeypatch):
    tone = [8000, -8000] * int(0.2 * SR / 2)
    gap_long = [0] * int(0.31 * SR)  # "드시고 | 가세요" 사이에 목소리가 넣은 쉼
    gap_short = [0] * int(0.06 * SR)  # 받침소리처럼 짧게 멈추는 곳
    pcm = array.array("h", tone + gap_long + tone + gap_short + tone).tobytes()
    out = tts.trim_silence(pcm)
    total = len(out) / 2 / SR
    expected = 0.6 + tts.MAX_PAUSE_S + 0.06  # 소리 0.2초 3개 + 줄인 쉼 + 그대로 둔 짧은 쉼
    assert abs(total - expected) < 0.03


def test_여러_문장은_무음을_잘라_0점2초_간격으로_이어_붙이고_문장은_다시_쓴다(client, fake_google):
    r = client.post("/api/tts", json={"text": "애플파이 하나 담았어요. 더 필요하신 건 있으세요?"})
    one = SPEECH_S + tts.LEAD_KEEP_S + tts.TAIL_KEEP_S
    assert abs(seconds(r.content) - (2 * one + tts.SENTENCE_GAP_S)) < 0.05
    client.post("/api/tts", json={"text": "빅맥 하나 담았어요. 더 필요하신 건 있으세요?"})
    assert len(fake_google) == 3  # "더 필요하신 건 있으세요?" 는 한 번만 만듦


def test_Google이_실패하면_503(client, monkeypatch):
    def post(url, params=None, json=None, timeout=None):
        return httpx.Response(403, json={"error": "denied"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(tts, "API_KEY", "test-key")
    monkeypatch.setattr(tts.httpx, "post", post)
    monkeypatch.setattr(tts, "_cache", type(tts._cache)())
    r = client.post("/api/tts", json={"text": "실패하는 문장"})
    assert r.status_code == 503
    assert "test-key" not in r.text  # 키가 응답에 새지 않음
