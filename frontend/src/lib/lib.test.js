import { describe, expect, it, vi } from 'vitest'
import { createBarcodeReader } from './barcode.js'
import { paginate } from './paginate.js'
import {
  choiceInfo,
  idleTimerAllowed,
  idleTimerRunning,
  isPaymentChoice,
  scannerAllowed,
  screenOf,
  sideOf,
} from './screen.js'

const res = (step, choices, cart) => ({ step, choices, cart })

describe('screenOf: 서버 응답 → 화면', () => {
  it('세션이 없으면 대기 화면', () => {
    expect(screenOf(null)).toBe('idle')
  })

  it('단계별 기본 화면', () => {
    expect(screenOf(res('DINE_TYPE', ['매장에서', '포장']))).toBe('dine')
    expect(screenOf(res('MENU', ['빅맥', '추천해 주세요']))).toBe('menu')
    expect(screenOf(res('CONFIRM', ['맞아요', '수정할게요']))).toBe('confirm')
  })

  it('옵션 단계는 버튼 글자로 세트/음료/사이즈를 구분', () => {
    expect(screenOf(res('OPTION', ['세트', '단품']))).toBe('option-set')
    expect(screenOf(res('OPTION', ['미디엄', '라지']))).toBe('option-size')
    expect(screenOf(res('OPTION', ['코카콜라', '코카콜라 제로', '스프라이트', '아메리카노', '오렌지 주스']))).toBe('option-drink')
  })

  it('쿠폰 단계 화면 4가지', () => {
    expect(screenOf(res('COUPON', ['쿠폰 있어요', '없어요']))).toBe('coupon-ask')
    expect(screenOf(res('COUPON', ['쿠폰 없이 결제할게요']))).toBe('coupon-scan')
    expect(screenOf(res('COUPON', ['쿠폰 없이 결제할게요', '직원 불러 주세요']))).toBe('coupon-problem')
    expect(screenOf(res('COUPON', ['담아 주세요', '쿠폰 없이 결제할게요']))).toBe('coupon-menu-missing')
  })

  it('결제 단계와 결제 실패', () => {
    expect(screenOf(res('PAYMENT', ['카드 결제']))).toBe('payment')
    expect(screenOf(res('PAYMENT', ['다시 결제할게요', '직원 불러 주세요']))).toBe('payment-fail')
  })

  it('어느 단계든 취소 확인이 먼저', () => {
    expect(screenOf(res('PAYMENT', ['네, 취소할게요', '아니요']))).toBe('cancel-confirm')
  })

  it('끝난 주문: 결제됐으면 완료, 취소됐으면 종료', () => {
    expect(screenOf(res('DONE', [], { status: 'paid' }))).toBe('done')
    expect(screenOf(res('DONE', [], { status: 'cancelled' }))).toBe('ended')
  })
})

describe('screenOf: 서버 화면 구분 값(question)이 있으면 그 값을 쓴다 (백엔드 PR #19)', () => {
  const q = (question, step = 'MENU', choices = []) => ({ question, step, choices })

  it('버튼 글자가 바뀌어도 question 으로 화면을 고른다', () => {
    expect(screenOf(q('SET_DRINK', 'OPTION', ['콜라 주세요']))).toBe('option-drink')
    expect(screenOf(q('SET_SIZE', 'OPTION', ['보통', '크게']))).toBe('option-size')
    expect(screenOf(q('SET_OR_SINGLE', 'OPTION', ['세트로', '단품으로']))).toBe('option-set')
  })

  it('쿠폰·결제 화면', () => {
    expect(screenOf(q('COUPON_ASK', 'COUPON'))).toBe('coupon-ask')
    expect(screenOf(q('COUPON_READ_FAILED', 'COUPON'))).toBe('coupon-scan')
    expect(screenOf(q('COUPON_READ_FAILED_TWICE', 'COUPON'))).toBe('coupon-problem')
    expect(screenOf(q('COUPON_UNUSABLE', 'COUPON'))).toBe('coupon-problem')
    expect(screenOf(q('COUPON_ADD_MENU', 'COUPON'))).toBe('coupon-menu-missing')
    expect(screenOf(q('PAYMENT_RETRY', 'PAYMENT'))).toBe('payment-fail')
  })

  it('메뉴 단계의 여러 질문은 모두 메뉴 화면', () => {
    ;['MENU', 'MENU_MORE', 'EDIT', 'RECOMMEND', 'SIMILAR_MENU'].forEach((code) => expect(screenOf(q(code))).toBe('menu'))
  })

  it('취소·완료', () => {
    expect(screenOf(q('CANCEL_CONFIRM', 'PAYMENT'))).toBe('cancel-confirm')
    expect(screenOf(q('CANCELLED', 'DONE'))).toBe('ended')
    expect(screenOf(q('DONE', 'DONE'))).toBe('done')
  })

  it('모르는 question 이면 예전처럼 버튼 글자로 짐작', () => {
    expect(screenOf(q('NEW_THING', 'OPTION', ['세트', '단품']))).toBe('option-set')
  })
})

describe('choiceInfo · sideOf', () => {
  it('버튼 정보(choice_items)를 글자로 찾는다', () => {
    const r = { choice_items: [{ label: '오렌지 주스', option_item_id: 9, extra_price: 700 }, { label: '아메리카노' }] }
    expect(choiceInfo(r, '오렌지 주스').extra_price).toBe(700)
    expect(choiceInfo(r, '없는 버튼')).toEqual({})
    expect(choiceInfo({}, '오렌지 주스')).toEqual({})
  })

  const sides = ['후렌치 후라이', '맥너겟 4조각', '치즈스틱 2조각']
  const options = [
    { option_item_id: 2, name: '라지' },
    { option_item_id: 3, name: '후렌치 후라이' },
    { option_item_id: 7, name: '코카콜라 제로' },
  ]

  it('세트의 지금 사이드를 찾는다 (예전 응답: 이름으로)', () => {
    expect(sideOf({ is_set: true, options }, sides).option_item_id).toBe(3)
  })

  it('새 응답은 group 값으로 찾는다', () => {
    const withGroup = options.map((o) => ({ ...o, group: o.option_item_id === 3 ? '세트 사이드' : '세트 음료' }))
    expect(sideOf({ is_set: true, options: withGroup }, []).name).toBe('후렌치 후라이')
  })

  it('단품은 사이드가 없다', () => {
    expect(sideOf({ is_set: false, options: [] }, sides)).toBeNull()
  })
})

describe('idleTimerRunning: 무응답 타이머를 세는지', () => {
  const base = { screen: 'payment', inPayment: false, busy: false, speaking: false, listening: false, warned: false }

  it('조용히 기다리는 중이면 센다', () => {
    expect(idleTimerRunning(base)).toBe(true)
  })

  it('안내를 읽는 중·손님 말을 듣는 중에는 멈춘다', () => {
    expect(idleTimerRunning({ ...base, speaking: true })).toBe(false)
    expect(idleTimerRunning({ ...base, listening: true })).toBe(false)
  })

  it('"도움이 필요하세요?"를 띄운 뒤에는 그 안내를 읽는 중에도 계속 센다 (안 그러면 처음 화면으로 영영 안 돌아감)', () => {
    expect(idleTimerRunning({ ...base, warned: true, speaking: true })).toBe(true)
  })

  it('카드를 넣은 뒤(결제 중)·서버 응답 대기·주문 완료에는 세지 않는다', () => {
    expect(idleTimerRunning({ ...base, inPayment: true, warned: true })).toBe(false)
    expect(idleTimerRunning({ ...base, busy: true })).toBe(false)
    expect(idleTimerRunning({ ...base, screen: 'done', warned: true })).toBe(false)
  })
})

describe('화면별 규칙', () => {
  it('결제 버튼만 결제 API로 보낸다', () => {
    expect(isPaymentChoice('카드 결제')).toBe(true)
    expect(isPaymentChoice('다시 결제할게요')).toBe(true)
    expect(isPaymentChoice('맞아요')).toBe(false)
  })

  it('주문 완료에는 무응답 타이머를 쓰지 않고, 결제 화면(카드 넣기 전)에서는 쓴다 (이슈 #14)', () => {
    expect(idleTimerAllowed('menu')).toBe(true)
    expect(idleTimerAllowed('payment')).toBe(true)
    expect(idleTimerAllowed('payment-fail')).toBe(true)
    expect(idleTimerAllowed('done')).toBe(false)
    expect(idleTimerAllowed('ended')).toBe(false)
  })

  it('쿠폰 화면에서만 바코드를 받는다', () => {
    expect(scannerAllowed('coupon-scan')).toBe(true)
    expect(scannerAllowed('menu')).toBe(false)
  })
})

describe('paginate: 한 화면 최대 4개', () => {
  it('4개 이하는 한 쪽', () => {
    expect(paginate(['a', 'b', 'c', 'd'])).toEqual([['a', 'b', 'c', 'd']])
  })

  it('음료 5개는 3개 + 2개 (넘기기 버튼 자리를 남김)', () => {
    expect(paginate(['1', '2', '3', '4', '5'])).toEqual([['1', '2', '3'], ['4', '5']])
  })
})

describe('createBarcodeReader: 스캐너 입력', () => {
  it('빠르게 들어온 글자 + Enter 를 바코드로 읽는다', () => {
    const onScan = vi.fn()
    const read = createBarcodeReader({ onScan })
    ;[...'TEST0001'].forEach((k, i) => read(k, 1000 + i * 10))
    read('Enter', 1100)
    expect(onScan).toHaveBeenCalledWith('TEST0001')
  })

  it('사람이 천천히 친 글자는 무시한다', () => {
    const onScan = vi.fn()
    const read = createBarcodeReader({ onScan })
    ;[...'TEST0001'].forEach((k, i) => read(k, 1000 + i * 500))
    read('Enter', 1000 + 8 * 500)
    expect(onScan).not.toHaveBeenCalled()
  })
})
