"""음성 인식 힌트: 지금 화면에서 손님이 할 법한 말을 모델 서버 /stt 에 넘긴다."""
import httpx

from app.routers import sessions as sessions_router


class FakeStt:
    def __init__(self, transcript):
        self.transcript = transcript
        self.sent = []

    async def post(self, url, files=None, data=None):
        self.sent.append(data)
        return httpx.Response(200, json={"transcript": self.transcript}, request=httpx.Request("POST", url))


def _voice(client, monkeypatch, sid, transcript):
    fake = FakeStt(transcript)

    class Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return fake

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(sessions_router.httpx, "AsyncClient", Client)
    r = client.post(f"/api/sessions/{sid}/voice", files={"audio": ("a.wav", b"RIFF....", "audio/wav")})
    return r.json(), fake.sent[0]


def test_식사_장소_화면은_포장_매장_힌트를_넘긴다(client, monkeypatch):
    sid = client.post("/api/sessions", json={"kiosk_id": 1}).json()["session_id"]
    body, sent = _voice(client, monkeypatch, sid, "포장해 주세요")
    hints = sent["hints"].split(",")
    assert "포장" in hints and "매장에서" in hints and "먹고 갈게요" in hints
    assert "빅맥" not in hints  # 메뉴 이름으로 끌려가지 않게
    assert body["cart"]["dine_type"] == "takeout"


def test_메뉴_화면은_힌트를_안_보내_모델_서버가_메뉴_이름_전체를_쓴다(client, monkeypatch):
    sid = client.post("/api/sessions", json={"kiosk_id": 1}).json()["session_id"]
    client.post(f"/api/sessions/{sid}/chat", json={"text": "포장"})
    _, sent = _voice(client, monkeypatch, sid, "빅맥 하나")
    assert sent is None
