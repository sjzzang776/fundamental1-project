"""말로 화면 조작: 쪽 넘기기·메뉴판 보기·다시 듣기. 화면은 actions 의 UI 명령을 따른다."""
import pytest


def _session(client):
    return client.post("/api/sessions", json={"kiosk_id": 1}).json()["session_id"]


def _say(client, sid, text):
    return client.post(f"/api/sessions/{sid}/chat", json={"text": text}).json()


def _ui(body):
    return [a for a in body["actions"] if a.get("type") == "UI"]


def _to_drink(client):
    sid = _session(client)
    _say(client, sid, "포장")
    _say(client, sid, "빅맥 세트 하나")
    return sid


@pytest.mark.parametrize("text", ["다른 음료 보여 줘", "다음 페이지로 넘겨 줘", "다른 거 보여 주세요", "넘겨 줘", "다음"])
def test_세트_음료_화면에서_다음_쪽(client, text):
    sid = _to_drink(client)
    b = _say(client, sid, text)
    assert _ui(b) == [{"type": "UI", "command": "next_page"}]
    assert b["step"] == "OPTION" and b["question"] == "SET_DRINK"  # 단계는 그대로
    assert not b["cart"]["items"]


@pytest.mark.parametrize("text", ["앞 쪽 보여 줘", "이전 페이지", "처음 음료로", "뒤로 가 줘"])
def test_앞_쪽(client, text):
    sid = _to_drink(client)
    assert _ui(_say(client, sid, text)) == [{"type": "UI", "command": "prev_page"}]


@pytest.mark.parametrize("text,category", [
    ("다른 햄버거 보여 줘", "버거"), ("음료 뭐 있어요", "음료"), ("디저트 보여 줘", "디저트"),
    ("메뉴판 보여 주세요", None), ("햄버거 종류 좀 보여 줘", "버거"),
])
def test_메뉴_화면에서_메뉴판을_그_종류로(client, text, category):
    sid = _session(client)
    _say(client, sid, "매장에서")
    b = _say(client, sid, text)
    assert _ui(b) == [{"type": "UI", "command": "show_menu", "category": category}]
    assert b["step"] == "MENU"


@pytest.mark.parametrize("text", ["다시 말해 줘", "뭐라고요?", "잘 안 들려요", "못 들었어"])
def test_다시_듣기는_지금_안내를_다시(client, text):
    sid = _session(client)
    first = _say(client, sid, "포장")
    again = _say(client, sid, text)
    assert again["reply_text"] == first["reply_text"].split("? ")[-1] or "어떤 걸 드시고 싶으세요?" in again["reply_text"]
    assert again["step"] == "MENU"


def test_메뉴판_닫기(client):
    sid = _session(client)
    _say(client, sid, "포장")
    assert _ui(_say(client, sid, "메뉴판 닫아 줘")) == [{"type": "UI", "command": "close_menu"}]


@pytest.mark.parametrize("text,intent", [
    ("빅맥 다음에 콜라도 주세요", "ADD_ITEM"),  # 메뉴가 있으면 주문
    ("다른 거로 바꿔 주세요", None),  # 수정 (쪽 넘기기 아님)
    ("더 없어요", "DENY"),  # 다 골랐다는 뜻 (쪽 넘기기 아님)
])
def test_화면_조작으로_잘못_보지_않는다(client, text, intent):
    sid = _session(client)
    _say(client, sid, "포장")
    b = _say(client, sid, text)
    assert not _ui(b)
    assert b["intent"] not in ("PAGE_NEXT", "PAGE_PREV", "SHOW_MENU", "CLOSE_MENU", "REPEAT")
    if intent:
        assert b["intent"] == intent
