"""의도 파악 C안: 규칙 먼저, 못 알아들을 때만 LLM(모델 서버 /nlu) 다시 쓰기. 실제 LLM 대신 가짜 응답으로 시험한다."""
import httpx
import pytest

from app.services import nlu


class FakeModel:
    """모델 서버 /nlu 흉내: 받은 말 → 다시 쓴 문장. 몇 번 불렸는지 기록한다."""

    def __init__(self, table=None, fail=False):
        self.table = table or {}
        self.fail = fail
        self.calls = []

    def post(self, url, json=None, timeout=None):
        self.calls.append(json)
        request = httpx.Request("POST", url)
        if self.fail:
            return httpx.Response(503, json={"error": {"code": "NLU_UNAVAILABLE"}}, request=request)
        rewrite = self.table.get(json["text"], "")
        return httpx.Response(200, json={"rewrite": rewrite, "confidence": 0.9 if rewrite else 0}, request=request)


@pytest.fixture()
def fake_model(monkeypatch):
    def install(**kwargs):
        model = FakeModel(**kwargs)
        monkeypatch.setattr(nlu.httpx, "post", model.post)
        monkeypatch.setattr(nlu, "_model_down_until", 0.0)
        return model

    return install


def _session(client):
    return client.post("/api/sessions", json={"kiosk_id": 1}).json()["session_id"]


def _say(client, sid, text):
    return client.post(f"/api/sessions/{sid}/chat", json={"text": text}).json()


def test_규칙으로_알아들으면_LLM을_부르지_않는다(client, fake_model):
    model = fake_model(table={})
    r = _say(client, _session(client), "포장이요")
    assert r["cart"]["dine_type"] == "takeout"
    assert model.calls == []


def test_못_알아들은_말만_LLM이_다시_써서_진행한다(client, fake_model):
    model = fake_model(table={"봉투에 담아 줘": "포장"})
    r = _say(client, _session(client), "봉투에 담아 줘")
    assert r["step"] == "MENU"
    assert r["cart"]["dine_type"] == "takeout"
    assert len(model.calls) == 1
    sent = model.calls[0]
    assert sent["step"] == "DINE_TYPE"
    assert "빅맥" in sent["menus"]  # LLM이 메뉴 이름 안에서만 고르도록 목록을 보낸다


def test_LLM이_다시_쓴_메뉴도_메뉴_DB로_확인한다(client, fake_model):
    fake_model(table={"그 매운 거 두 개": "맥스파이시 상하이 버거 2개 주세요"})
    sid = _session(client)
    _say(client, sid, "매장에서")
    r = _say(client, sid, "그 매운 거 두 개")
    assert r["step"] in {"OPTION", "MENU"}
    assert r["actions"] and r["actions"][0]["type"] == "ADD_ITEM"


def test_LLM이_없는_메뉴를_말해도_담지_않는다(client, fake_model):
    fake_model(table={"짜장면 줘": "짜장면 1개 주세요"})
    sid = _session(client)
    _say(client, sid, "매장에서")
    r = _say(client, sid, "짜장면 줘")
    assert not (r["cart"] or {}).get("items")


def test_모델_서버가_실패하면_규칙_결과대로_다시_묻는다(client, fake_model):
    model = fake_model(fail=True)
    sid = _session(client)
    r = _say(client, sid, "봉투에 담아 줘")
    assert r["step"] == "DINE_TYPE"  # LLM 없이 규칙 결과대로 다시 묻는다
    assert len(model.calls) == 1
    # 실패 뒤 잠시 동안은 모델 서버를 다시 부르지 않는다 (손님을 기다리게 하지 않게)
    _say(client, sid, "어쩌구저쩌구")
    assert len(model.calls) == 1
