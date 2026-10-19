// 서버 응답을 보고 어떤 화면을 보여 줄지 정한다.
// 백엔드 PR #19부터 응답에 화면 구분 값 `question` 이 있어서 그 값을 먼저 쓴다.
// question 이 없는 예전 응답이면 step + 버튼 글자(choices)로 짐작한다.

export const CHOICE = {
  CARD_PAY: '카드 결제',
  RETRY_PAY: '다시 결제할게요',
  NO_COUPON: '쿠폰 없이 결제할게요',
  ADD_COUPON_MENU: '담아 주세요',
  CANCEL_YES: '네, 취소할게요',
  STAFF: '직원 불러 주세요',
}

// 진행 표시(ProgressBar)에 쓰는 단계 번호와 이름
export const PROGRESS = {
  DINE_TYPE: { index: 1, label: '먹는 곳' },
  MENU: { index: 2, label: '메뉴 고르기' },
  OPTION: { index: 3, label: '자세히 고르기' },
  CONFIRM: { index: 4, label: '주문 확인' },
  COUPON: { index: 5, label: '쿠폰' },
  PAYMENT: { index: 6, label: '결제' },
}
export const PROGRESS_TOTAL = 6

// 백엔드 question 값 → 화면 (노션 API 명세 · 백엔드 PR #19)
const BY_QUESTION = {
  DINE_TYPE: 'dine',
  MENU: 'menu',
  MENU_MORE: 'menu',
  EDIT: 'menu',
  RECOMMEND: 'menu',
  SIMILAR_MENU: 'menu',
  SET_OR_SINGLE: 'option-set',
  SET_DRINK: 'option-drink',
  SET_SIZE: 'option-size',
  SET_SIDE: 'option-side',
  OPTION: 'option-other',
  CONFIRM: 'confirm',
  COUPON_ASK: 'coupon-ask',
  COUPON_SCAN: 'coupon-scan',
  COUPON_READ_FAILED: 'coupon-scan',
  COUPON_READ_FAILED_TWICE: 'coupon-problem',
  COUPON_UNUSABLE: 'coupon-problem',
  COUPON_ADD_MENU: 'coupon-menu-missing',
  PAYMENT: 'payment',
  PAYMENT_RETRY: 'payment-fail',
  CANCEL_CONFIRM: 'cancel-confirm',
  CANCELLED: 'ended',
  DONE: 'done',
}

export function screenOf(res) {
  if (!res) return 'idle'
  return BY_QUESTION[res.question] ?? guessScreen(res)
}

// question 이 없을 때(예전 백엔드): 버튼 글자로 짐작
function guessScreen({ step, choices = [], cart }) {
  const has = (c) => choices.includes(c)

  if (has(CHOICE.CANCEL_YES)) return 'cancel-confirm'

  switch (step) {
    case 'DINE_TYPE':
      return 'dine'
    case 'MENU':
      return 'menu'
    case 'OPTION':
      if (has('세트') && has('단품')) return 'option-set'
      if (has('미디엄') || has('라지')) return 'option-size'
      return 'option-drink'
    case 'CONFIRM':
      return 'confirm'
    case 'COUPON':
      if (has('쿠폰 있어요')) return 'coupon-ask'
      if (has(CHOICE.ADD_COUPON_MENU)) return 'coupon-menu-missing'
      if (has(CHOICE.STAFF)) return 'coupon-problem'
      return 'coupon-scan'
    case 'PAYMENT':
      if (has(CHOICE.RETRY_PAY)) return 'payment-fail'
      return 'payment'
    case 'DONE':
      return cart && cart.status !== 'cancelled' && cart.status !== 'cart' ? 'done' : 'ended'
    default:
      return 'menu'
  }
}

// 버튼 하나에 붙은 정보 (choice_items: menu_id·가격·사진 또는 option_item_id·추가 금액). 없으면 빈 객체
export function choiceInfo(res, label) {
  return res?.choice_items?.find((item) => item.label === label) ?? {}
}

// 버튼을 눌렀을 때 /chat 대신 결제 API를 불러야 하는 버튼
export function isPaymentChoice(choice) {
  return choice === CHOICE.CARD_PAY || choice === CHOICE.RETRY_PAY
}

// 무응답 타이머를 쓰지 않는 화면. 결제 화면은 카드를 넣기 전까지는 타이머를 쓴다
// (손님이 떠나면 주문을 정리해 쿠폰이 묶이지 않게 · 이슈 #14). 카드를 넣은 뒤에는 Kiosk 에서 멈춘다.
export function idleTimerAllowed(screen) {
  return !['idle', 'done', 'ended'].includes(screen)
}

// 무응답 타이머를 지금 세고 있어야 하는지.
// 안내를 읽는 중·듣는 중에는 멈추지만, "도움이 필요하세요?"(warned)를 띄운 뒤에는 그 안내를 읽는 중에도 계속 센다.
// (멈추면 타이머가 처음부터 다시 세어 "도움이 필요하세요?"만 반복되고 처음 화면으로 돌아가지 않는다)
// 손님 말을 듣는 중(마이크 버튼을 누르고 말하는 중)에는 안내 뒤에도 멈춘다 (말하는 도중에 처음 화면으로 가지 않게)
export function idleTimerRunning({ screen, inPayment, busy, speaking, listening, warned }) {
  if (!idleTimerAllowed(screen) || inPayment || busy || listening) return false
  return warned || !speaking
}

// 바코드 스캐너 입력을 받는 화면
export function scannerAllowed(screen) {
  return ['coupon-ask', 'coupon-scan', 'coupon-problem', 'coupon-menu-missing'].includes(screen)
}

// 세트 사이드 옵션 (확인 화면 "사이드: 후렌치 후라이 [바꾸기]")
export const SIDE_GROUP = '세트 사이드'

export function sideOf(item, sideNames) {
  if (!item.is_set) return null
  return item.options.find((o) => (o.group ? o.group === SIDE_GROUP : sideNames.includes(o.name))) ?? null
}
