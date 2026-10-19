// 손님 화면 전체. 서버 응답 → 어떤 화면인지(screenOf) → 그 화면의 본문을 공통 틀 안에 그린다.
// 공통 틀 (위에서 아래로): 진행 표시 · 안내 말풍선 · 마이크 · 본문(버튼) · 하단 고정 바
import { useCallback, useEffect, useState } from 'react'
import AgentBubble from '../components/AgentBubble.jsx'
import BottomBar from '../components/BottomBar.jsx'
import ChoiceList from '../components/ChoiceList.jsx'
import MicIndicator from '../components/MicIndicator.jsx'
import Modal from '../components/Modal.jsx'
import ProgressBar from '../components/ProgressBar.jsx'
import { useBarcodeScanner } from '../hooks/useBarcodeScanner.js'
import { useIdleTimer } from '../hooks/useIdleTimer.js'
import { useKioskSession } from '../hooks/useKioskSession.js'
import { useMenuCatalog } from '../hooks/useMenuCatalog.js'
import { useVoice } from '../hooks/useVoice.js'
import { idleTimerAllowed, scannerAllowed, screenOf } from '../lib/screen.js'
import CompleteScreen from './CompleteScreen.jsx'
import ConfirmScreen from './ConfirmScreen.jsx'
import CouponScreen from './CouponScreen.jsx'
import IdleScreen from './IdleScreen.jsx'
import KioskStage from './KioskStage.jsx'
import MenuBrowser from './MenuBrowser.jsx'
import MenuScreen from './MenuScreen.jsx'
import OptionScreen from './OptionScreen.jsx'
import PaymentScreen from './PaymentScreen.jsx'

const ENDED_RETURN_MS = 5000
const PAYMENT_TEXT = {
  insert: '카드를 화면 아래 빛나는 곳에 꽂아 주세요.',
  processing: '결제하고 있어요. 카드를 빼지 말아 주세요.',
}

export default function Kiosk() {
  const k = useKioskSession()
  const catalog = useMenuCatalog()
  const [browsing, setBrowsing] = useState(false)
  const voice = useVoice({ onRecorded: (blob) => k.sendVoice(blob) })

  const { res, payment } = k
  const screen = screenOf(res)
  const inPayment = Boolean(payment)
  const text = payment ? PAYMENT_TEXT[payment.phase] : res?.reply_text

  // 새 안내 문장이 오면 소리 내어 읽어 준다
  useEffect(() => {
    if (text) voice.speak(text)
  }, [res, payment?.phase]) // eslint-disable-line react-hooks/exhaustive-deps

  // 무응답 15초 → "도움이 필요하세요?" → 15초 더 → 처음 화면 (결제 중·말하는 중·듣는 중에는 멈춤)
  const warned = useIdleTimer({
    enabled: idleTimerAllowed(screen) && !inPayment && !k.busy && !voice.speaking && voice.micState !== 'listening',
    resetKey: res,
    onTimeout: () => {
      setBrowsing(false)
      voice.stopSpeaking()
      k.endByTimeout()
    },
  })
  useEffect(() => {
    if (warned) voice.speak('도움이 필요하세요?')
  }, [warned]) // eslint-disable-line react-hooks/exhaustive-deps

  // 쿠폰 화면에서만 바코드 스캐너 입력을 받는다
  useBarcodeScanner(scannerAllowed(screen) && !k.busy, k.scanCoupon)

  // 주문이 취소·종료되면 잠깐 안내하고 처음 화면으로
  useEffect(() => {
    if (screen !== 'ended') return undefined
    const t = setTimeout(k.reset, ENDED_RETURN_MS)
    return () => clearTimeout(t)
  }, [screen, k.reset])

  const goHome = useCallback(() => {
    voice.stopSpeaking()
    k.reset()
  }, [k.reset]) // eslint-disable-line react-hooks/exhaustive-deps

  if (screen === 'idle') {
    return (
      <KioskStage>
        <IdleScreen onStart={k.start} busy={k.busy} />
      </KioskStage>
    )
  }

  const micState = k.voiceDown || voice.micState === 'error' ? 'error' : k.busy ? 'thinking' : voice.micState === 'listening' ? 'listening' : voice.speaking ? 'speaking' : 'idle'
  const agentState = micState === 'error' ? 'idle' : micState
  const choices = res.choices ?? []
  const common = { choices, onChoose: k.choose, disabled: k.busy }

  let body
  switch (screen) {
    case 'menu':
      body = <MenuScreen {...common} cart={res.cart} catalog={catalog} onBrowse={() => setBrowsing(true)} />
      break
    case 'option-set':
    case 'option-drink':
    case 'option-size':
      body = <OptionScreen {...common} screen={screen} optionPrice={catalog.optionPrice} />
      break
    case 'confirm':
      body = <ConfirmScreen {...common} cart={res.cart} onChangeQuantity={k.changeQuantity} />
      break
    case 'coupon-ask':
    case 'coupon-scan':
    case 'coupon-problem':
    case 'coupon-menu-missing':
      body = <CouponScreen {...common} screen={screen} onScan={k.scanCoupon} />
      break
    case 'payment':
    case 'payment-fail':
      body = (
        <PaymentScreen {...common} cart={res.cart} payment={payment} onFinish={k.finishPayment} onCancel={k.cancelPayment} />
      )
      break
    case 'done':
      body = <CompleteScreen order={k.order} onHome={goHome} />
      break
    case 'ended':
      body = <p className="ended">잠시 후 처음 화면으로 돌아가요.</p>
      break
    default:
      // dine, cancel-confirm 등: 서버가 준 버튼을 그대로
      body = (
        <ChoiceList
          {...common}
          describe={(c) => ({ icon: { 매장에서: '🍽️', 포장: '🛍️', '네, 취소할게요': '🗑️', 아니요: '↩' }[c] })}
        />
      )
  }

  const finished = screen === 'done' || screen === 'ended'

  return (
    <KioskStage>
      <div className="kiosk">
        <ProgressBar step={finished ? null : res.step} />
        <AgentBubble text={text} state={agentState} transcript={res.transcript} />
        {!finished && (
          <MicIndicator
            state={micState}
            disabled={inPayment}
            onPress={voice.micState === 'listening' ? voice.stopListening : voice.startListening}
          />
        )}
        <main className={`kiosk__body kiosk__body--${screen}`}>{body}</main>
        {!finished && (
          <BottomBar
            staffOnly={inPayment}
            disabled={k.busy}
            onRestart={() => k.say('처음으로')}
            onCancel={() => k.say('취소')}
            onStaff={() => k.callStaff()}
          />
        )}

        {browsing && screen === 'menu' && (
          <MenuBrowser catalog={catalog} onAdd={k.addItem} onClose={() => setBrowsing(false)} />
        )}

        {warned && (
          <Modal
            icon="🙋"
            title="도움이 필요하세요?"
            text="아무것도 누르지 않으시면 잠시 후 처음 화면으로 돌아가요."
            actions={[
              { label: '계속할게요', onClick: () => {} },
              { label: '직원 부르기', variant: 'secondary', onClick: () => k.callStaff() },
              { label: '처음으로', variant: 'secondary', onClick: () => k.say('처음으로') },
            ]}
          />
        )}
        {k.modal && !warned && (
          <Modal
            icon={k.modal.type === 'staff' ? '🙋' : k.modal.type === 'voice' ? '🔇' : '⚠️'}
            title={k.modal.type === 'staff' ? '직원을 불렀어요' : '잠깐만요'}
            text={k.modal.text}
            actions={
              k.modal.type === 'error'
                ? [
                    { label: '다시 해 볼게요', onClick: k.refresh },
                    { label: '직원 부르기', variant: 'secondary', onClick: () => k.callStaff() },
                  ]
                : [{ label: '괜찮아요, 계속할게요', onClick: k.closeModal }]
            }
          />
        )}
      </div>
    </KioskStage>
  )
}
