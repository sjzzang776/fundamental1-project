// 서버 응답(step + choices)을 보고 어떤 화면을 보여 줄지 정한다.
// OPTION·COUPON·PAYMENT 단계는 화면이 여러 개인데 응답에 구분 값이 없어서 버튼 글자로 구분한다.
// (백엔드에 awaiting/question 필드 추가를 요청해 둠: frontend/docs/frontend-plan.md 7번)

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

export function screenOf(res) {
  if (!res) return 'idle'
  const { step, choices = [], cart } = res
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

// 버튼을 눌렀을 때 /chat 대신 결제 API를 불러야 하는 버튼
export function isPaymentChoice(choice) {
  return choice === CHOICE.CARD_PAY || choice === CHOICE.RETRY_PAY
}

// 무응답 타이머를 멈춰야 하는 화면 (결제 중·주문 끝)
export function idleTimerAllowed(screen) {
  return !['idle', 'payment', 'payment-fail', 'done', 'ended'].includes(screen)
}

// 바코드 스캐너 입력을 받는 화면
export function scannerAllowed(screen) {
  return ['coupon-ask', 'coupon-scan', 'coupon-problem', 'coupon-menu-missing'].includes(screen)
}
