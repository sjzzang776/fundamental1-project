"""기획서 5-1 기본 흐름 · 5-2 예외 흐름을 API로 따라가 보는 테스트."""


def start(client):
    body = client.post("/api/sessions", json={"kiosk_id": 1}).json()
    assert body["step"] == "DINE_TYPE"
    return body["session_id"]


def say(client, sid, text):
    r = client.post(f"/api/sessions/{sid}/chat", json={"text": text})
    assert r.status_code == 200, r.text
    return r.json()


def pay(client, order_id, key, success=True, amount=None):
    p = client.post(f"/api/orders/{order_id}/payments", json={"method": "card"}, headers={"Idempotency-Key": key})
    assert p.status_code == 201, p.text
    p = p.json()
    return client.post(
        "/api/payments/confirm",
        json={"payment_id": p["payment_id"], "amount": p["amount"] if amount is None else amount, "success": success},
    ).json()


def voice_order_until_payment(client, sid):
    say(client, sid, "먹고 갈게요")
    b = say(client, sid, "불고기버거 세트 하나 줘")
    assert b["step"] == "OPTION" and "음료" in b["reply_text"]
    b = say(client, sid, "콜라")
    assert "사이즈" in b["reply_text"]
    b = say(client, sid, "미디엄")
    assert b["cart"]["total_amount"] == 4500
    b = say(client, sid, "주문할게요")
    assert b["step"] == "CONFIRM" and "4,500원" in b["reply_text"]
    b = say(client, sid, "응")
    assert b["step"] == "COUPON"
    return b


# ---------- 메뉴 ----------

def test_menus_match_erd(client):
    menus = client.get("/api/menus").json()
    assert len(menus) == 19
    assert [m["name"] for m in menus if m["is_recommended"]] == ["빅맥", "맥스파이시 상하이 버거", "불고기 버거"]


def test_menu_detail_has_set_options(client, menu_ids):
    detail = client.get(f"/api/menus/{menu_ids['빅맥']}").json()
    assert [g["name"] for g in detail["option_groups"]] == ["세트 사이즈", "세트 사이드", "세트 음료"]


# ---------- 버튼 주문 ----------

def test_button_order_price_matches_erd_example(client, menu_ids, option_ids):
    sid = start(client)
    say(client, sid, "매장에서")
    # ERD 예: 빅맥 라지 세트 + 맥너겟 + 제로콜라 = 8,500원
    r = client.post(
        f"/api/sessions/{sid}/cart/items",
        json={"menu_id": menu_ids["빅맥"], "is_set": True,
              "option_item_ids": [option_ids["라지"], option_ids["맥너겟 4조각"], option_ids["코카콜라 제로"]]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["cart"]["total_amount"] == 8500


def test_set_without_required_option_is_rejected(client, menu_ids, option_ids):
    sid = start(client)
    r = client.post(f"/api/sessions/{sid}/cart/items", json={"menu_id": menu_ids["빅맥"], "is_set": True, "option_item_ids": [option_ids["라지"]]})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "INVALID_OPTION"


# ---------- 음성(대화) 주문 ----------

def test_voice_order_full_flow(client):
    sid = start(client)
    b = voice_order_until_payment(client, sid)
    b = say(client, sid, "없어요")
    assert b["step"] == "PAYMENT" and "카드" in b["reply_text"]
    result = pay(client, b["cart"]["order_id"], "k1")
    assert result["order_status"] == "paid" and result["order_number"] == 1
    assert "주문번호는 1번" in result["reply_text"]


def test_change_option_at_confirm(client):
    sid = start(client)
    say(client, sid, "포장")
    say(client, sid, "빅맥 세트")
    say(client, sid, "콜라")
    say(client, sid, "라지")
    b = say(client, sid, "주문할게요")
    b = say(client, sid, "콜라 말고 사이다")
    assert b["step"] == "CONFIRM"
    assert "스프라이트" in b["cart"]["items"][0]["label"]


def test_one_more_and_remove(client):
    sid = start(client)
    say(client, sid, "매장")
    say(client, sid, "애플파이 두 개")
    b = say(client, sid, "하나 더")
    assert b["cart"]["items"][0]["quantity"] == 3
    b = say(client, sid, "애플파이 빼줘")
    assert b["cart"]["items"] == []


def test_recommend_and_ask_menu(client):
    sid = start(client)
    say(client, sid, "매장")
    b = say(client, sid, "뭐가 맛있어?")
    assert "빅맥" in b["reply_text"] and b["choices"][0] == "빅맥"
    b = say(client, sid, "빅맥 얼마야?")
    assert "5,500원" in b["reply_text"]


def test_unknown_speech_and_unknown_menu(client):
    sid = start(client)
    b = say(client, sid, "음 그러니까")
    assert "다시 한번 말씀해 주세요" in b["reply_text"]
    say(client, sid, "매장")
    b = say(client, sid, "피자 주세요")
    assert "그 메뉴는 없어요" in b["reply_text"]


def test_cancel_needs_confirmation(client):
    sid = start(client)
    b = say(client, sid, "취소")
    assert "취소할까요" in b["reply_text"]
    b = say(client, sid, "네, 취소할게요")
    assert b["step"] == "DONE"
    r = client.post(f"/api/sessions/{sid}/chat", json={"text": "빅맥"})
    assert r.status_code == 410


def test_staff_call(client):
    sid = start(client)
    b = say(client, sid, "직원 불러줘")
    assert "직원을 불렀어요" in b["reply_text"]
    calls = client.get("/api/staff-calls").json()
    assert calls[0]["reason"] == "user_request"


# ---------- 쿠폰 (기획서 5-1의 5단계, 5-2 쿠폰 예외) ----------

def test_percent_coupon(client):
    sid = start(client)
    voice_order_until_payment(client, sid)
    b = client.post(f"/api/sessions/{sid}/coupon", json={"barcode": "TEST0003"}).json()
    assert b["step"] == "PAYMENT"
    assert b["cart"]["discount_amount"] == 450 and b["cart"]["total_amount"] == 4050


def test_expired_and_used_coupons(client):
    sid = start(client)
    voice_order_until_payment(client, sid)
    b = client.post(f"/api/sessions/{sid}/coupon", json={"barcode": "TEST0004"}).json()
    assert "기간이 끝난" in b["reply_text"]
    b = client.post(f"/api/sessions/{sid}/coupon", json={"barcode": "TEST0005"}).json()
    assert "이미 사용한" in b["reply_text"]
    assert b["cart"]["coupon"] is None


def test_unreadable_barcode_twice_offers_staff(client):
    sid = start(client)
    voice_order_until_payment(client, sid)
    b = client.post(f"/api/sessions/{sid}/coupon", json={"barcode": "???"}).json()
    assert "밝기" in b["reply_text"]
    b = client.post(f"/api/sessions/{sid}/coupon", json={"barcode": "???"}).json()
    assert "직원을 불러 드릴까요" in b["reply_text"]
    say(client, sid, "직원 불러 주세요")
    assert client.get("/api/staff-calls").json()[0]["reason"] == "barcode_failed"


def test_coupon_menu_missing_offers_to_add(client):
    sid = start(client)
    voice_order_until_payment(client, sid)  # 불고기 버거 세트 4,500원
    say(client, sid, "쿠폰 있어요")
    b = client.post(f"/api/sessions/{sid}/coupon", json={"barcode": "TEST0002"}).json()
    assert "쿠폰 메뉴를 담아 드릴까요" in b["reply_text"]
    b = say(client, sid, "담아 주세요")
    assert b["step"] == "CONFIRM" and len(b["cart"]["items"]) == 2  # 후렌치 후라이 추가 → 6,800원
    b = say(client, sid, "맞아요")
    assert b["step"] == "PAYMENT"
    assert b["cart"]["discount_amount"] == 2300 and b["cart"]["total_amount"] == 4500


def test_coupon_min_amount(client):
    sid = start(client)
    say(client, sid, "포장")
    say(client, sid, "감자튀김 하나")  # 2,300원 < 5,000원
    say(client, sid, "주문할게요")
    say(client, sid, "네")
    b = client.post(f"/api/sessions/{sid}/coupon", json={"barcode": "TEST0002"}).json()
    assert "5,000원 이상" in b["reply_text"]


def test_set_coupon_adds_set_and_asks_options(client):
    sid = start(client)
    voice_order_until_payment(client, sid)
    client.post(f"/api/sessions/{sid}/coupon", json={"barcode": "TEST0001"})
    b = say(client, sid, "담아 주세요")
    assert b["step"] == "OPTION" and "음료" in b["reply_text"]
    say(client, sid, "제로콜라")
    b = say(client, sid, "기본으로")
    assert b["step"] == "CONFIRM"
    b = say(client, sid, "맞아요")
    assert b["step"] == "PAYMENT" and b["cart"]["discount_amount"] == 1000


def test_coupon_is_used_only_once(client):
    sid = start(client)
    voice_order_until_payment(client, sid)
    b = client.post(f"/api/sessions/{sid}/coupon", json={"barcode": "TEST0003"}).json()
    pay(client, b["cart"]["order_id"], "k-a")
    sid2 = start(client)
    voice_order_until_payment(client, sid2)
    b = client.post(f"/api/sessions/{sid2}/coupon", json={"barcode": "TEST0003"}).json()
    assert "이미 사용한" in b["reply_text"]


# ---------- 결제 ----------

def test_payment_is_idempotent_and_numbers_increase(client):
    sid = start(client)
    b = voice_order_until_payment(client, sid)
    order_id = b["cart"]["order_id"]
    say(client, sid, "없어요")
    first = client.post(f"/api/orders/{order_id}/payments", headers={"Idempotency-Key": "same"}).json()
    again = client.post(f"/api/orders/{order_id}/payments", headers={"Idempotency-Key": "same"}).json()
    assert first["payment_id"] == again["payment_id"]
    client.post("/api/payments/confirm", json={"payment_id": first["payment_id"], "amount": first["amount"]})

    sid2 = start(client)
    b2 = voice_order_until_payment(client, sid2)
    say(client, sid2, "없어요")
    assert pay(client, b2["cart"]["order_id"], "other")["order_number"] == 2


def test_payment_failure_then_retry(client):
    sid = start(client)
    b = voice_order_until_payment(client, sid)
    order_id = b["cart"]["order_id"]
    say(client, sid, "없어요")
    failed = pay(client, order_id, "try1", success=False)
    assert failed["status"] == "failed" and "결제가 안 됐어요" in failed["reply_text"]
    wrong = pay(client, order_id, "try2", amount=1)
    assert wrong["fail_reason"] == "AMOUNT_MISMATCH"
    ok = pay(client, order_id, "try3")
    assert ok["order_status"] == "paid"


def test_payment_requires_idempotency_key(client):
    sid = start(client)
    b = voice_order_until_payment(client, sid)
    r = client.post(f"/api/orders/{b['cart']['order_id']}/payments")
    assert r.status_code == 400 and r.json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"


# ---------- 주방 · 호출 화면 ----------

def test_kitchen_done_shows_on_pickup_board(client):
    sid = start(client)
    b = voice_order_until_payment(client, sid)
    say(client, sid, "없어요")
    result = pay(client, b["cart"]["order_id"], "k")
    assert client.get("/api/pickup-board").json() == {"cooking": [1], "ready": []}
    r = client.patch(f"/api/kitchen/orders/{result['order_id']}", json={"status": "ready"})
    assert r.status_code == 200
    assert client.get("/api/pickup-board").json() == {"cooking": [], "ready": [1]}
    r = client.patch(f"/api/kitchen/orders/{result['order_id']}", json={"status": "cooking"})
    assert r.status_code == 409
