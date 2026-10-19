// 매장 화면(호출 화면·주방 화면)이 쓰는 API
import { request } from './client.js'

// 매장에 둘 때는 frontend/.env 에 VITE_KITCHEN_TOKEN 을 넣는다 (비어 있으면 보내지 않음)
const KITCHEN_TOKEN = import.meta.env.VITE_KITCHEN_TOKEN
const kitchenHeaders = KITCHEN_TOKEN ? { 'X-Kitchen-Token': KITCHEN_TOKEN } : {}

export const storeApi = {
  pickupBoard: () => request('/api/pickup-board'),
  kitchenOrders: () => request('/api/kitchen/orders', { headers: kitchenHeaders }),
  setOrderStatus: (orderId, status) =>
    request(`/api/kitchen/orders/${orderId}`, { method: 'PATCH', body: { status }, headers: kitchenHeaders }),
  staffCalls: () => request('/api/staff-calls?resolved=false', { headers: kitchenHeaders }),
  // 시연 전: 테스트 쿠폰 TEST0001~0005 를 처음 상태로 (백엔드 PR #19 · 이슈 #14)
  resetDemoCoupons: () => request('/api/demo/reset-coupons', { method: 'POST', headers: kitchenHeaders }),
  resolveStaffCall: (callId) =>
    request(`/api/staff-calls/${callId}`, { method: 'PATCH', body: { resolved: true }, headers: kitchenHeaders }),
}
