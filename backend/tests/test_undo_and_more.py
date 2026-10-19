"""되돌리기("잘못 말했어", "전으로 돌아가 줘")와 어르신 손님이 자주 하는 말."""
import pytest


def _session(client):
    return client.post("/api/sessions", json={"kiosk_id": 1}).json()["session_id"]


def _say(client, sid, text):
    return client.post(f"/api/sessions/{sid}/chat", json={"text": text}).json()


def _names(body):
    return [i["menu_name"] for i in (body["cart"] or {}).get("items", [])]


@pytest.mark.parametrize("text", ["잘못 말했어", "전으로 돌아가 줘", "방금 잘못 말해서 뒤로 가 줘", "방금 거 취소해 줘", "되돌려 줘"])
def test_세트를_고르는_중에_되돌리면_그_메뉴를_빼고_메뉴_고르기로(client, text):
    sid = _session(client)
    _say(client, sid, "포장")
    assert _say(client, sid, "불고기 버거 세트 하나")["step"] == "OPTION"
    b = _say(client, sid, text)
    assert b["intent"] == "UNDO"
    assert b["step"] == "MENU" and not _names(b)
    assert "담지 않을게요" in b["reply_text"]


def test_메뉴_단계에서_되돌리면_방금_담은_메뉴만_뺀다(client):
    sid = _session(client)
    _say(client, sid, "포장")
    _say(client, sid, "빅맥 단품 하나")
    _say(client, sid, "치즈버거 단품 하나")
    b = _say(client, sid, "잘못 말했어")
    assert b["step"] == "MENU"
    assert len(b["cart"]["items"]) == 1 and "빅맥" in b["cart"]["items"][0]["menu_name"]
    assert "방금 담은" in b["reply_text"]


def test_아무것도_없으면_식사_장소로(client):
    sid = _session(client)
    _say(client, sid, "매장에서")
    b = _say(client, sid, "전으로 돌아가 줘")
    assert b["step"] == "DINE_TYPE" and b["cart"]["dine_type"] is None


def test_주문_확인에서_되돌리면_메뉴_고르기로_쿠폰에서는_주문_확인으로(client):
    sid = _session(client)
    _say(client, sid, "포장")
    _say(client, sid, "빅맥 단품 하나")
    assert _say(client, sid, "주문할게요")["step"] == "CONFIRM"
    assert _say(client, sid, "뒤로 가 줘")["step"] == "MENU"
    _say(client, sid, "주문할게요")
    assert _say(client, sid, "맞아요")["step"] == "COUPON"
    b = _say(client, sid, "잘못 눌렀어요")
    assert b["step"] == "CONFIRM" and _names(b)


def test_다_해서_얼마예요는_합계(client):
    sid = _session(client)
    _say(client, sid, "포장")
    _say(client, sid, "빅맥 단품 하나")
    b = _say(client, sid, "다 해서 얼마예요?")
    assert b["intent"] == "TOTAL_PRICE" and "5,500원" in b["reply_text"]


def test_다_빼_줘는_장바구니만_비우고_주문은_계속(client):
    sid = _session(client)
    _say(client, sid, "포장")
    _say(client, sid, "빅맥 단품 하나")
    b = _say(client, sid, "다 빼 줘")
    assert b["intent"] == "CLEAR_CART" and not _names(b) and b["step"] == "MENU"
    assert b["cart"]["dine_type"] == "takeout"


@pytest.mark.parametrize("text,speed", [("천천히 말해 주세요", "slower"), ("너무 빨라요", "slower"),
                                        ("크게 말해 줘", "louder"), ("잘 안 들려요", "louder"), ("좀 빨리 말해", "faster")])
def test_안내_빠르기_크기(client, text, speed):
    sid = _session(client)
    b = _say(client, sid, text)
    assert {"type": "UI", "command": "voice", "speed": speed} in b["actions"]
    assert "드시고 가세요" in b["reply_text"]  # 지금 안내를 다시


@pytest.mark.parametrize("text,reply", [("잠깐만요", "천천히 고르세요"), ("생각 좀 해 볼게요", "천천히 고르세요"),
                                        ("안녕하세요", "안녕하세요"), ("고마워요", "고마워요")])
def test_기다려_달라는_말과_인사는_다시_말해_달라고_하지_않는다(client, text, reply):
    sid = _session(client)
    b = _say(client, sid, text)
    assert reply in b["reply_text"] and "다시 한번 말씀해" not in b["reply_text"]


def test_주문_전체_취소는_그대로(client):
    sid = _session(client)
    _say(client, sid, "포장")
    b = _say(client, sid, "주문 취소해 줘")
    assert b["intent"] == "CANCEL_ORDER"


def test_tts_빠르기를_받는다(client, monkeypatch):
    from app.services import tts
    seen = []

    def fake(text, speed="normal"):
        seen.append(speed)
        return b"MP3"

    monkeypatch.setattr(tts, "synthesize", fake)
    assert client.post("/api/tts", json={"text": "안녕하세요", "speed": "slower"}).status_code == 200
    assert seen == ["slower"]
    assert client.post("/api/tts", json={"text": "안녕하세요", "speed": "이상한값"}).status_code == 400
