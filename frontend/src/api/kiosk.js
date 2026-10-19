// 키오스크(손님 화면)가 쓰는 API. 노션 "API 명세" 페이지와 같은 이름·순서.
import { request } from './client.js'

export const KIOSK_ID = 1

export const kioskApi = {
  categories: () => request('/api/categories'),
  menus: () => request('/api/menus'),
  menuDetail: (menuId) => request(`/api/menus/${menuId}`),

  start: () => request('/api/sessions', { method: 'POST', body: { kiosk_id: KIOSK_ID } }),
  getSession: (id) => request(`/api/sessions/${id}`),
  end: (id, reason) => request(`/api/sessions/${id}?reason=${reason}`, { method: 'DELETE' }),

  // 버튼을 누르면 버튼 글자를 그대로 보낸다 (말로 한 것과 같게 처리됨)
  chat: (id, text) => request(`/api/sessions/${id}/chat`, { method: 'POST', body: { text } }),
  voice: (id, blob) => {
    const form = new FormData()
    form.append('audio', blob, 'voice.webm')
    return request(`/api/sessions/${id}/voice`, { method: 'POST', form })
  },

  addItem: (id, item) => request(`/api/sessions/${id}/cart/items`, { method: 'POST', body: item }),
  updateItem: (id, itemId, change) =>
    request(`/api/sessions/${id}/cart/items/${itemId}`, { method: 'PATCH', body: change }),
  removeItem: (id, itemId) => request(`/api/sessions/${id}/cart/items/${itemId}`, { method: 'DELETE' }),

  scanCoupon: (id, barcode) => request(`/api/sessions/${id}/coupon`, { method: 'POST', body: { barcode } }),
  staffCall: (id, reason = 'user_request') =>
    request(`/api/sessions/${id}/staff-call`, { method: 'POST', body: { reason } }),

  // 모의 결제: 결제 요청 → (카드 단말 대신 화면의 연습용 버튼) → 결제 결과 확인
  requestPayment: (orderId, idempotencyKey) =>
    request(`/api/orders/${orderId}/payments`, {
      method: 'POST',
      body: { method: 'card' },
      headers: { 'Idempotency-Key': idempotencyKey },
    }),
  confirmPayment: (payment, success) =>
    request('/api/payments/confirm', {
      method: 'POST',
      body: {
        payment_id: payment.payment_id,
        amount: payment.amount,
        success,
        fail_reason: success ? null : 'TEST_DECLINED',
      },
    }),
  getOrder: (orderId) => request(`/api/orders/${orderId}`),
}
