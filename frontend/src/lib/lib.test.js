import { describe, expect, it, vi } from 'vitest'
import { createBarcodeReader } from './barcode.js'
import { paginate } from './paginate.js'
import { idleTimerAllowed, isPaymentChoice, scannerAllowed, screenOf } from './screen.js'

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

describe('화면별 규칙', () => {
  it('결제 버튼만 결제 API로 보낸다', () => {
    expect(isPaymentChoice('카드 결제')).toBe(true)
    expect(isPaymentChoice('다시 결제할게요')).toBe(true)
    expect(isPaymentChoice('맞아요')).toBe(false)
  })

  it('결제 중·주문 완료에는 무응답 타이머를 쓰지 않는다', () => {
    expect(idleTimerAllowed('menu')).toBe(true)
    expect(idleTimerAllowed('payment')).toBe(false)
    expect(idleTimerAllowed('done')).toBe(false)
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
