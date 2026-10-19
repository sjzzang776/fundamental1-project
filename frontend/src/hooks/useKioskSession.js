// 키오스크 주문 상태를 한곳에서 관리한다.
// 화면은 "마지막 서버 응답(res)"을 그리기만 하고, 금액·다음 단계는 서버가 정한다.
import { useCallback, useRef, useState } from 'react'
import { kioskApi } from '../api/kiosk.js'
import { isPaymentChoice } from '../lib/screen.js'

const newKey = () =>
  globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`

export function useKioskSession() {
  const [res, setRes] = useState(null) // 마지막 발화 응답 (session_id, step, reply_text, choices, cart)
  const [payment, setPayment] = useState(null) // { phase: 'insert' | 'processing', data }
  const [order, setOrder] = useState(null) // 결제 완료된 주문 (주문번호 화면)
  const [modal, setModal] = useState(null) // { type: 'staff' | 'error' | 'voice', text }
  const [busy, setBusy] = useState(false)
  const [voiceDown, setVoiceDown] = useState(false)
  const resRef = useRef(null)
  resRef.current = res

  const reset = useCallback(() => {
    setRes(null)
    setPayment(null)
    setOrder(null)
    setModal(null)
    setBusy(false)
  }, [])

  const sessionId = () => resRef.current?.session_id

  const refresh = useCallback(async () => {
    if (!sessionId()) return
    try {
      setRes(await kioskApi.getSession(sessionId()))
      setModal(null)
    } catch {
      setModal({ type: 'error', text: '서버와 연결이 잠깐 끊겼어요. 다시 해 보시거나 직원을 불러 주세요.' })
    }
  }, [])

  // 모든 서버 요청을 감싸서 기획서 예외 흐름대로 처리한다
  const run = useCallback(
    async (task) => {
      setBusy(true)
      try {
        const body = await task()
        if (body && body.session_id) {
          setRes(body)
          if (body.intent === 'CALL_STAFF') setModal({ type: 'staff', text: '직원을 불렀어요. 잠시만 기다려 주세요.' })
        }
        return body
      } catch (err) {
        if (err.status === 410 || err.code === 'SESSION_NOT_FOUND') {
          reset() // 시간이 지나 끝난 주문 → 처음 화면
        } else if (err.code === 'MODEL_UNAVAILABLE') {
          setVoiceDown(true)
          setModal({ type: 'voice', text: '음성이 잠깐 안 돼요. 화면의 버튼을 눌러 주세요.' })
        } else if (err.code === 'INVALID_STATE') {
          await refresh() // 화면과 서버 단계가 어긋남 → 서버 기준으로 다시 그림
        } else {
          setModal({ type: 'error', text: `${err.message}. 다시 해 보시거나 직원을 불러 주세요.` })
        }
        return null
      } finally {
        setBusy(false)
      }
    },
    [refresh, reset],
  )

  const start = useCallback(() => run(() => kioskApi.start()), [run])
  const say = useCallback((text) => run(() => kioskApi.chat(sessionId(), text)), [run])
  const sendVoice = useCallback((blob) => run(() => kioskApi.voice(sessionId(), blob)), [run])
  const addItem = useCallback((item) => run(() => kioskApi.addItem(sessionId(), item)), [run])
  const changeQuantity = useCallback(
    (item, delta) => {
      const quantity = item.quantity + delta
      if (quantity <= 0) return run(() => kioskApi.removeItem(sessionId(), item.item_id))
      return run(() => kioskApi.updateItem(sessionId(), item.item_id, { quantity }))
    },
    [run],
  )
  // 확인 화면 사이드 바꾸기: 지금 사이드만 새 사이드로 바꾼 옵션 목록을 보낸다.
  // (백엔드 PR #19는 사이드 하나만 보내도 되지만, 전체를 보내면 예전 백엔드에서도 똑같이 동작한다)
  const changeSide = useCallback(
    (item, oldSide, newSide) => {
      const ids = item.options.map((o) => (o.option_item_id === oldSide.option_item_id ? newSide.id : o.option_item_id))
      return run(() => kioskApi.updateItem(sessionId(), item.item_id, { option_item_ids: ids }))
    },
    [run],
  )
  const scanCoupon = useCallback((barcode) => run(() => kioskApi.scanCoupon(sessionId(), barcode)), [run])

  const callStaff = useCallback(
    async (reason = 'user_request') => {
      if (!sessionId()) return
      const body = await run(() => kioskApi.staffCall(sessionId(), reason))
      if (body) setModal({ type: 'staff', text: body.reply_text })
    },
    [run],
  )

  // 무응답 15초 + 15초 → 서버에 timeout 으로 알리고 처음 화면
  const endByTimeout = useCallback(async () => {
    const id = sessionId()
    reset()
    if (id) await kioskApi.end(id, 'timeout').catch(() => {})
  }, [reset])

  // [카드 결제] [다시 결제할게요]: 모의 결제라 /chat 대신 결제 API를 직접 부른다.
  // 네트워크 오류로 다시 보낼 때만 같은 Idempotency-Key 를 써서 중복 결제를 막는다.
  const pay = useCallback(async () => {
    const orderId = resRef.current?.cart?.order_id
    const key = newKey()
    const data = await run(async () => {
      try {
        return await kioskApi.requestPayment(orderId, key)
      } catch (err) {
        if (err.code === 'NETWORK_ERROR') return kioskApi.requestPayment(orderId, key)
        throw err
      }
    })
    if (data) setPayment({ phase: 'insert', data })
  }, [run])

  // 카드 단말 대신 화면의 연습용 버튼이 결제 결과를 알려 준다
  const finishPayment = useCallback(
    async (success) => {
      if (!payment) return
      setPayment({ ...payment, phase: 'processing' })
      await new Promise((r) => setTimeout(r, 1200)) // "결제하고 있어요" 화면을 잠깐 보여 줌
      const result = await run(() => kioskApi.confirmPayment(payment.data, success))
      setPayment(null)
      if (!result) return
      const prev = resRef.current
      if (result.order_status === 'paid') {
        const done = await kioskApi.getOrder(result.order_id).catch(() => null)
        setOrder(done ?? { order_number: result.order_number })
        setRes({
          ...prev,
          step: 'DONE',
          question: result.question ?? 'DONE',
          reply_text: result.reply_text,
          choices: [],
          choice_items: [],
          cart: { ...prev.cart, status: 'paid' },
        })
      } else {
        setRes({
          ...prev,
          step: result.step,
          question: result.question ?? null,
          reply_text: result.reply_text,
          choices: result.choices,
          choice_items: result.choice_items ?? [],
        })
      }
    },
    [payment, run],
  )

  const cancelPayment = useCallback(() => setPayment(null), [])

  const choose = useCallback((choice) => (isPaymentChoice(choice) ? pay() : say(choice)), [pay, say])

  return {
    res,
    payment,
    order,
    modal,
    busy,
    voiceDown,
    closeModal: () => setModal(null),
    start,
    choose,
    say,
    sendVoice,
    addItem,
    changeQuantity,
    changeSide,
    scanCoupon,
    callStaff,
    finishPayment,
    cancelPayment,
    endByTimeout,
    refresh,
    reset,
  }
}
