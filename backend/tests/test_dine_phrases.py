import pytest

# 식사 장소를 묻는 첫 질문에 손님이 실제로 하는 말 (버튼 글자 외)
DINE_IN = ["매장에서", "먹고 가", "먹고가요", "먹고 갈게요", "여기서 먹을게요", "여기서요", "안에서 먹을게", "앉아서 먹을게요"]
TAKEOUT = ["포장", "포장이요", "포장해줘", "테이크아웃", "들고 가", "들고갈게요", "가져갈게요", "가지고 갈게요",
           "갖고 갈게요", "싸 주세요", "싸줘", "집에 가서 먹을게요"]


def _answer(client, text):
    sid = client.post("/api/sessions", json={"kiosk_id": 1}).json()["session_id"]
    return client.post(f"/api/sessions/{sid}/chat", json={"text": text}).json()


@pytest.mark.parametrize("text", DINE_IN)
def test_dine_in_phrases(client, text):
    r = _answer(client, text)
    assert r["step"] == "MENU"
    assert r["cart"]["dine_type"] == "dine_in"


@pytest.mark.parametrize("text", TAKEOUT)
def test_takeout_phrases(client, text):
    r = _answer(client, text)
    assert r["step"] == "MENU"
    assert r["cart"]["dine_type"] == "takeout"
