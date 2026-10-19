"""안내 음성 /api/tts: 사람 목소리(Google TTS)를 만들고 저장해 다시 쓴다. 실제 Google 대신 가짜 응답으로 시험한다."""
import base64

import httpx
import pytest

from app.services import tts


@pytest.fixture()
def fake_google(monkeypatch):
    calls = []

    def post(url, params=None, json=None, timeout=None):
        calls.append(json)
        audio = base64.b64encode(("MP3:" + json["input"]["text"]).encode()).decode()
        return httpx.Response(200, json={"audioContent": audio}, request=httpx.Request("POST", url))

    monkeypatch.setattr(tts, "API_KEY", "test-key")
    monkeypatch.setattr(tts.httpx, "post", post)
    monkeypatch.setattr(tts, "_cache", type(tts._cache)())
    return calls


def test_키가_없으면_503_화면은_브라우저_목소리로(client, monkeypatch):
    monkeypatch.setattr(tts, "API_KEY", "")
    r = client.post("/api/tts", json={"text": "안녕하세요"})
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "TTS_UNAVAILABLE"


def test_사람_목소리_MP3를_돌려주고_같은_문장은_다시_만들지_않는다(client, fake_google):
    for _ in range(3):
        r = client.post("/api/tts", json={"text": "드시고 가세요, 포장하세요?"})
        assert r.status_code == 200
        assert r.headers["content-type"] == "audio/mpeg"
        assert r.content == "MP3:드시고 가세요, 포장하세요?".encode()
    assert len(fake_google) == 1  # 두 번째부터는 저장해 둔 음성
    assert fake_google[0]["voice"]["name"] == tts.VOICE


def test_Google이_실패하면_503(client, monkeypatch):
    def post(url, params=None, json=None, timeout=None):
        return httpx.Response(403, json={"error": "denied"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(tts, "API_KEY", "test-key")
    monkeypatch.setattr(tts.httpx, "post", post)
    monkeypatch.setattr(tts, "_cache", type(tts._cache)())
    r = client.post("/api/tts", json={"text": "실패하는 문장"})
    assert r.status_code == 503
    assert "test-key" not in r.text  # 키가 응답에 새지 않음
