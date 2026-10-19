# 프론트엔드 작업 계획서 · 음성 주문 키오스크

> 작성일: 2026-10-19 · 담당: 프론트엔드
> 근거: 노션 [📐 기획서](https://app.notion.com/p/3fb4c3788823815083a2c071cb6feca1), [🔌 API 명세](https://app.notion.com/p/3fb4c378882381f59122fb25e293b710) (변경 이력 2026-10-19까지),
> 백엔드 1차 구현(PR #4, `origin/main`), Figma 1·2차 디자인, `frontend/docs/figma-ui-prompt.md`

---

## 1. 지금 상태

| 항목 | 상태 |
|---|---|
| 디자인 | Figma 1차(화면 25장 + 부품 10종), 2차(맥도날드 스타일) 완료 |
| 코드 | `frontend/src/App.jsx` 는 연결 테스트 화면뿐 (health, predict). 키오스크 화면은 아직 없음 |
| 백엔드 | 키오스크 API 거의 전부 구현됨. 웹훅만 미구현(PG사 결정 후) |
| 모델 | STT(`/voice`) 구현됨(PR #5, #8). TTS(`/api/tts`)는 아직 502 |
| 브랜치 | `feat/frontend-first-task` 가 main보다 10커밋 뒤처짐 → **작업 전에 main 최신화 필요** |

---

## 2. 백엔드 요청 5가지에 대한 프론트 답

| # | 백엔드 요청 | 프론트가 할 일 |
|---|---|---|
| 1 | 버튼 글자를 그대로 `POST /chat` | `choices` 버튼을 누르면 `{text: 버튼글자}` 로 전송. **예외: 결제 단계 버튼은 결제 API를 부름** (5번, 6-1 참고) |
| 2 | 무응답 15초 → "도움이 필요하세요?" → 15초 → `DELETE ?reason=timeout` | 무응답 타이머 훅 구현. 결제 단계·주문 완료 화면·음성 안내/녹음 중에는 타이머 멈춤 |
| 3 | 세트 음료 5개 (규칙 3~4개 초과) | **제안: 한 화면 최대 4칸, 넘치면 2페이지.** 1쪽 [코카콜라] [코카콜라 제로] [스프라이트] [다른 음료 보기 ▶], 2쪽 [아메리카노] [오렌지 주스 +700원] [◀ 처음 음료]. 말로는 5개 모두 언제든 고를 수 있음. `choices` 가 5개 이상인 모든 화면에 같은 규칙 적용 |
| 4 | 쿠폰 바코드 → `POST /coupon` | 바코드 스캐너 입력(키보드처럼 글자+Enter가 들어옴)을 받아서 전송. 못 쓰는 쿠폰도 200이므로 `reply_text`·`choices` 를 그대로 보여 줌 |
| 5 | 모의 결제 | `POST /orders/{id}/payments` → `POST /payments/confirm {success:true}`. 카드 단말이 없으니 **개발용 [결제 성공] [결제 실패] 버튼**을 화면 구석에 둠 |

---

## 3. 화면 흐름과 API 연결표

모든 화면은 서버 응답의 `step` 하나로 정합니다. 화면은 **응답을 그리기만** 하고, 금액 계산·다음 단계 결정은 서버가 합니다.

| step | 화면 (Figma 프레임) | 버튼(`choices`) 예시 | 부르는 API |
|---|---|---|---|
| (세션 없음) | `00-idle` 대기 화면 | [주문 시작] | `POST /api/sessions {kiosk_id:1}` |
| `DINE_TYPE` | `01-dine-option` | [매장에서] [포장] | `POST /chat` |
| `MENU` | `02-menu-recommend` 추천 3개 + 사진·가격 | [빅맥] [맥스파이시 상하이 버거] [불고기 버거] [추천해 주세요] / 담은 뒤 [주문할게요] | `POST /chat` (사진·가격은 `GET /api/menus` 에서 이름으로 찾아 붙임) |
| `MENU` (직접 고르기) | 카테고리 탭 + 메뉴 목록 | — | `GET /api/categories`, `GET /api/menus?category_id=`, `GET /api/menus/{id}`, `POST /cart/items` |
| `OPTION` | `03a-option-set` | [세트] [단품] | `POST /chat` |
| `OPTION` | `03b-option-drink` (2페이지) | 음료 5개 | `POST /chat` |
| `OPTION` | `03c-option-size` | [미디엄] [라지] | `POST /chat` |
| `CONFIRM` | `04-order-confirm` 장바구니 큰 글씨 | [맞아요] [수정할게요] | `POST /chat` (각 항목 [빼기] [하나 더] 는 `PATCH`/`DELETE /cart/items/{item_id}`) |
| `COUPON` | `05a-coupon-ask` | [쿠폰 있어요] [없어요] | `POST /chat` |
| `COUPON` | `05b-coupon-scan` 바코드 위치 움직이는 그림 | [쿠폰 없이 결제할게요] | 스캐너 → `POST /coupon` |
| `COUPON` | `e05`~`e08` 쿠폰 실패·사용 불가·쿠폰 메뉴 없음 | [쿠폰 없이 결제할게요] [직원 불러 주세요] / [담아 주세요] | `POST /chat` |
| `PAYMENT` | `05c-coupon-applied`(할인 있으면) → `06b-payment-insert` | [카드 결제] | **결제 API** (6-1) |
| `PAYMENT` | `06c-payment-processing` 결제 중 | 없음 | — |
| `PAYMENT` | `e09-payment-fail` | [다시 결제할게요] [직원 불러 주세요] | 다시 결제 API / `POST /staff-call {reason:"payment_failed"}` |
| `DONE` | `07-order-complete` 주문번호 크게 | 없음 | `GET /api/orders/{order_id}` → 10초 뒤 대기 화면 |

※ `OPTION`(세트/음료/사이즈)과 `COUPON`(묻기/스캔/실패)은 같은 step 안에 화면이 여러 개입니다. 지금 응답에는 "어떤 질문인지" 값이 없어서 **`choices` 글자를 보고 구분**해야 합니다 → 백엔드에 필드 추가 요청 (7번).

---

## 4. 언제든 쓰는 하단 버튼 · 예외 처리

| 상황 | 화면 | 처리 |
|---|---|---|
| [처음으로] | 모든 화면 하단 | `POST /chat {text:"처음으로"}` → 서버가 장바구니 비우고 `DINE_TYPE` 으로 |
| [취소] | 모든 화면 하단 | `POST /chat {text:"취소"}` → "주문을 취소할까요?" [네, 취소할게요] [아니요] → 취소되면 대기 화면 |
| [직원 부르기] | 모든 화면 하단 | `POST /staff-call {reason:"user_request"}` → `e04-staff-called` |
| 못 알아들음 | `e01` | 서버가 `reply_text` 로 "다시 한번 말씀해 주세요…" 를 줌. 화면은 그대로 그림 |
| 메뉴에 없음 | `e03` | 서버 안내 문장 그대로 표시 |
| 무응답 15초 | `e02-need-help` | 모달 "도움이 필요하세요?" [계속할게요] [직원 부르기]. 15초 더 → `DELETE /sessions/{id}?reason=timeout` → 대기 화면 |
| 410 `SESSION_EXPIRED` | — | 대기 화면으로 |
| 409 `INVALID_STATE` | — | `GET /sessions/{id}` 로 다시 읽어 화면 맞추기 |
| 502/503 `MODEL_UNAVAILABLE` | 마이크 아이콘 "음성이 안 돼요" | 음성만 끄고 버튼 주문 계속 |
| 네트워크 끊김 | 안내 모달 | 같은 요청 1번 다시 시도 → 실패하면 [직원 부르기] 안내 |

---

## 5. 매장 화면 (가로 1920×1080)

| 화면 | API | 방식 |
|---|---|---|
| `s01-pickup-call` 호출 화면 | `GET /api/pickup-board` | 3초마다 다시 읽기. 새로 `ready` 된 번호는 크게 깜빡이고 "123번 고객님, 음식이 나왔어요." 읽어 주기 |
| `s02-kitchen-orders` 주방 | `GET /api/kitchen/orders`, `PATCH /api/kitchen/orders/{id} {status:"ready"}` | 3초마다 다시 읽기. MVP는 [완료] 버튼만. 헤더 `X-Kitchen-Token` (값은 `.env`) |
| 직원 호출 알림 (주방 화면 위쪽) | `GET /api/staff-calls?resolved=false`, `PATCH /api/staff-calls/{id} {resolved:true}` | "키오스크 1번 · 결제 단계 · 결제 실패" 알림 + [처리했어요] |

주소 나누기: `/` 키오스크, `/pickup` 호출 화면, `/kitchen` 주방 (React Router 추가 또는 `location.pathname` 으로 간단 분기).

---

## 6. 기술 메모

### 6-1. 결제 순서
1. [카드 결제] 누름 → `POST /api/orders/{cart.order_id}/payments`, 헤더 `Idempotency-Key: crypto.randomUUID()`
   - 네트워크 오류로 다시 보낼 때는 **같은 키** 를 씀 (중복 결제 방지). [다시 결제할게요] 는 **새 키**.
2. 응답 `payment_id`, `amount` 를 저장 → `06b` 카드 꽂기 화면
3. (개발용 버튼) → `POST /api/payments/confirm {payment_id, amount, success:true|false}`
4. 응답 `order_status:"paid"` → `07` 주문번호 화면 / `status:"failed"` → `e09`
- 결제 중에는 무응답 타이머·[처음으로]를 막음 (기획서: "결제 중에는 적용하지 않음")

### 6-2. 바코드 스캐너
- USB 스캐너는 키보드처럼 글자를 빠르게 치고 Enter를 누름 → `keydown` 을 모아 두었다가 Enter에서 전송
- `COUPON` 단계(스캔 화면)에서만 받음. 개발용으로 화면 구석에 입력칸도 둠
- 테스트 쿠폰: `TEST0001`(빅맥 세트 1,000원) `TEST0002`(후라이 무료, 5,000원 이상) `TEST0003`(10%) `TEST0004`(기간 끝남) `TEST0005`(이미 사용), 없는 값 → 읽기 실패

### 6-3. 음성
- 녹음: `MediaRecorder` 로 webm 녹음, 최대 15초 → `POST /voice` (multipart `audio`). 응답의 `transcript` 를 "이렇게 들었어요: …" 로 잠깐 표시
- 음성 안내: `POST /api/tts` 가 아직 502 → **당분간 브라우저 `speechSynthesis`(한국어)로 대신** 읽고, TTS가 되면 바꿈. 음성이 실패해도 글자·버튼으로 계속 진행
- 마이크 상태 표시: 듣고 있어요 / 말하는 중 / 잠시만요 / 음성이 안 돼요

### 6-4. 폴더 구조 (제안)
```
src/
├─ api/            client.js(fetch·에러 처리), kiosk.js, store.js(주방·호출)
├─ hooks/          useKioskSession.js(세션·응답 상태), useIdleTimer.js, useBarcodeScanner.js, useVoice.js
├─ components/     Figma 부품 10종: Button, ChoiceButton, MenuCard, AgentBubble, MicIndicator,
│                  ProgressBar, CartItem, BottomBar, Modal, GuideAnimation
├─ screens/        00-idle … 07-order-complete, e01 … e09 (Figma 프레임 이름과 같게)
├─ store-screens/  PickupBoard, KitchenOrders
└─ styles/         tokens.css (Figma kiosk/color·글자 규칙)
```
- 상태 관리: 별도 라이브러리 없이 `useReducer` 하나로 "마지막 서버 응답"을 들고 있음 (화면 = 응답을 그린 것)

---

## 7. 백엔드(Gilbert)에게 물어볼 것 · 요청

1. **화면 구분 값 추가 요청**: 응답에 `awaiting`(예: `COUPON_SCAN`, `PAYMENT_RETRY`, `ADD_COUPON_MENU`, `CANCEL_CONFIRM`)이나 `question`(예: `SET`, `세트 음료`, `세트 사이즈`) 같은 값을 넣어 줄 수 있는지. 지금은 버튼 글자로 짐작해야 해서 문구가 바뀌면 화면이 깨짐
2. **버튼의 가격·사진**: `choices` 가 글자뿐이라 [오렌지 주스 +700원], 추천 메뉴 사진·가격을 보이려면 프론트가 이름으로 메뉴를 찾아야 함. `choices` 옆에 `menu_id`/`extra_price` 를 함께 주는 방식이 가능한지 (어려우면 이름 매칭으로 진행)
3. **주문 완료 후**: 몇 초 뒤 대기 화면으로 돌아갈지 (제안 10초). 세션은 결제 완료 때 서버가 이미 끝내므로 `DELETE` 는 안 불러도 되는지
4. **결제 단계에서 멈춘 주문 정리**: 손님이 결제 화면에서 그냥 떠나면 그 주문이 `pending_payment` 로 계속 남음. 새 세션을 열 때(`POST /sessions`)도, 서버 무응답 정리(`SESSION_IDLE_LIMIT_SEC`)도 결제 단계는 건너뜀. 그 주문에 쿠폰이 붙어 있으면 그 쿠폰이 "이미 사용한 쿠폰"이 되어 다시 못 씀 (2026-10-19 화면 테스트 중 TEST0001 로 실제로 겪음). 결제 단계도 일정 시간(예: 3분) 지나면 정리하거나, 결제 요청 없이 머문 경우는 정리하는 방법이 가능한지

※ `/voice` 는 2026-10-19 확인 결과 동작함 (소리 없는 녹음 → "다시 한번 말씀해 주세요"). `/api/tts` 는 아직 502라 브라우저 읽어 주기로 대신함.
※ 결제 단계 버튼([카드 결제] [다시 결제할게요])은 모의 결제라 따로 묻지 않고, 프론트가 결제 API(`/orders/{id}/payments` → `/payments/confirm`)를 직접 부르는 방식으로 진행합니다.

---

## 8. 작업 순서 (단계별)

| 단계 | 할 일 | 끝났다는 기준 |
|---|---|---|
| 0. 준비 | main 최신화(브랜치에 main 합치기), `docker compose up --build`, `/docs` 에서 기본 흐름 직접 눌러 보기, 7번 질문 보내기 | Swagger로 주문 1건 결제까지 해 봄 |
| 1. 기반 | `api/client.js`(에러 형식 `{error:{code,message}}` 처리), `useKioskSession`, 디자인 토큰 CSS, 공통 부품 10종, 화면 골격(진행 표시·말풍선·버튼·하단 바) | 빈 화면에서 골격이 1080×1920 비율로 보임 |
| 2. 기본 흐름 | 00 → 01 → 02 → 03a/b/c → 04 를 버튼만으로 연결. 음료 2페이지 | 버튼만 눌러 빅맥 세트를 장바구니에 담고 주문 확인까지 감 |
| 3. 쿠폰·결제 | 05a/b/c, 바코드 입력, 06b/c, 모의 결제, 07 주문번호 | TEST0001~0005 각각 기획서대로 안내가 나오고, 결제 성공·실패 둘 다 확인 |
| 4. 예외 | 하단 바 3개, 무응답 타이머, e01~e09, 410/409/502 처리 | 30초 가만히 두면 대기 화면으로 돌아감, 결제 중엔 안 돌아감 |
| 5. 음성 | 녹음 → `/voice`, 마이크 상태, `speechSynthesis` 안내 | "불고기버거 세트 하나 줘" 로 장바구니에 담김. 음성 서버 꺼도 버튼으로 끝까지 주문됨 |
| 6. 매장 화면 | `/pickup`, `/kitchen`, 직원 호출 알림 | 키오스크에서 결제 → 주방에 뜸 → [완료] → 호출 화면에 번호 뜸 |
| 7. 마무리 | 접근성 점검(글씨 크기·대비 7:1·버튼 120px·선택지 4개 이하), `npm run build` 통과, PR | 기획서 5-1·5-2 표를 하나씩 눌러 보며 체크 |

P0(필수)는 0~6단계 전부입니다. 시간이 남으면(P1): 주방 "조리 중" 상태, 메뉴 직접 고르기 화면 꾸미기, 호출 화면 음성 안내.
