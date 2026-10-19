// 대화 흐름 시험: 실제 백엔드 테스트(test_kiosk_flow.py)와 비슷한 주문을 데모 대화에 넣어 본다
import { handle, newSession, pay, itemLabel, total } from '../dialog.js'
const runs = [
  ['포장해 주세요', '불고기 버거 세트 하나 주세요', '제로 콜라로', '라지', '다 골랐어요', '맞아요', '카드로 할게요'],
  ['먹고 갈게요', '매운 닭 버거 두 개 단품으로', '감자튀김 하나 주세요', '주문할게요', '아니요 수정할게요', '감자튀김 빼 주세요', '주문할게요', '맞아요'],
  ['포장', '치즈버거 세트 큰 걸로 사이다', '주문할게요', '콜라 말고 사이다로 바꿔 주세요', '사이다 말고 제로콜라로 바꿔 주세요', '하나 더 주세요', '맞아요'],
  ['포장', '피자 주세요', '추천해 주세요', '새우 버거', '세트', '기본으로 주세요', '기본', '잘못 말했어', '다 해서 얼마예요', '취소할래요', '네'],
]
for (const run of runs) {
  const s = newSession()
  console.log('---')
  for (const t of run) {
    const r = handle(s, t)
    console.log(`손님: ${t}\n  [${s.step}] ${r.reply}`)
    if (r.actions.includes('pay')) { const d = pay(s); console.log(`  [${s.step}] ${d.reply.replace(/\d+번/, 'NNN번')}`) }
  }
  console.log('  장바구니:', s.cart.map((i) => `${itemLabel(i)}×${i.quantity}`).join(' / '), '합계', total(s))
}
