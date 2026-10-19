// s02-kitchen-orders: 주방 주문 관리 (가로 1920 × 1080). 주소: /kitchen
// MVP: 결제된 주문 목록 + [완료] 버튼. 위쪽에 직원 호출 알림(어느 키오스크, 어느 단계)을 띄운다.
import { storeApi } from '../api/store.js'
import KioskStage from '../screens/KioskStage.jsx'
import { usePolling } from './usePolling.js'

const STEP_NAME = {
  DINE_TYPE: '먹는 곳 고르기',
  MENU: '메뉴 고르기',
  OPTION: '자세히 고르기',
  CONFIRM: '주문 확인',
  COUPON: '쿠폰',
  PAYMENT: '결제',
  DONE: '주문 끝',
}
const REASON = { user_request: '손님이 불렀어요', payment_failed: '결제가 안 됐어요', barcode_failed: '쿠폰을 못 읽었어요' }

export default function KitchenOrders() {
  const orders = usePolling(storeApi.kitchenOrders)
  const calls = usePolling(storeApi.staffCalls)

  const act = async (fn) => {
    await fn().catch(() => {})
    orders.reload()
    calls.reload()
  }

  return (
    <KioskStage width={1920} height={1080}>
      <div className="kitchen">
        {calls.data?.length > 0 && (
          <div className="staff-alerts">
            {calls.data.map((c) => (
              <div key={c.staff_call_id} className="staff-alert">
                <span>
                  🙋 키오스크 {c.kiosk_id}번 · {STEP_NAME[c.step] ?? c.step} · {REASON[c.reason] ?? c.reason}
                </span>
                <button type="button" className="btn btn--primary btn--small" onClick={() => act(() => storeApi.resolveStaffCall(c.staff_call_id))}>
                  처리했어요
                </button>
              </div>
            ))}
          </div>
        )}
        <header className="kitchen__head">
          <h1>주방 주문</h1>
          <span>{orders.error ? '⚠️ 서버와 연결이 끊겼어요' : `${orders.data?.length ?? 0}건`}</span>
        </header>
        <div className="kitchen__grid">
          {orders.data?.map((o) => (
            <article key={o.order_id} className={`ticket ticket--${o.status}`}>
              <header>
                <b>{o.order_number}번</b>
                <span>{o.dine_type === 'takeout' ? '🛍️ 포장' : '🍽️ 매장'}</span>
              </header>
              <ul>
                {o.items.map((i) => (
                  <li key={i.label}>
                    {i.label} × {i.quantity}
                  </li>
                ))}
              </ul>
              {o.status === 'ready' ? (
                <button type="button" className="btn btn--secondary" onClick={() => act(() => storeApi.setOrderStatus(o.order_id, 'picked_up'))}>
                  ✅ 가져감
                </button>
              ) : (
                <button type="button" className="btn btn--primary" onClick={() => act(() => storeApi.setOrderStatus(o.order_id, 'ready'))}>
                  완료
                </button>
              )}
            </article>
          ))}
        </div>
      </div>
    </KioskStage>
  )
}
