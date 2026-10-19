// 실행 방법 (전체를 docker compose up 으로 켠 뒤, 저장소 맨 위 폴더에서):
// docker run --rm --network fundamental1-project_default -v "$PWD/frontend/e2e:/e2e" -v "$PWD/frontend/docs/screenshots:/out" -w /e2e \
//   mcr.microsoft.com/playwright:v1.49.1-noble sh -c "npm init -y >/dev/null && npm i playwright@1.49.1 >/dev/null && node kiosk-flow.mjs"
// ※ 쿠폰 TEST0001 을 쓰므로, 그 쿠폰을 쓴 결제 대기 주문이 남아 있으면 실패할 수 있다.

// 키오스크 화면을 처음부터 끝까지 자동으로 눌러 보고 단계마다 사진을 찍는다.
import { chromium } from 'playwright'

const BASE = process.env.BASE || 'http://frontend'
const OUT = process.env.OUT || '/out'
const log = (...a) => console.log(...a)
const results = []
const check = (name, ok, extra = '') => {
  results.push({ name, ok })
  log(`${ok ? 'PASS' : 'FAIL'} ${name} ${extra}`)
}

// 시작 전에 테스트 쿠폰을 처음 상태로 (백엔드 PR #19의 시연용 기능. 없으면 넘어감)
const reset = await fetch(`${BASE}/api/demo/reset-coupons`, { method: 'POST' }).catch(() => null)
log(`쿠폰 초기화: ${reset?.status ?? '연결 안 됨'}`)

const browser = await chromium.launch()
const kiosk = await browser.newPage({ viewport: { width: 540, height: 960 }, deviceScaleFactor: 2 })
const errors = []
kiosk.on('pageerror', (e) => errors.push(String(e)))

const shot = (page, name) => page.screenshot({ path: `${OUT}/${name}.jpg`, type: 'jpeg', quality: 80 })
const wait = (ms = 900) => kiosk.waitForTimeout(ms)
const bubble = () => kiosk.locator('.agent__text').innerText()
const choice = (label) => kiosk.locator('.choice').filter({ has: kiosk.locator('.choice__label', { hasText: new RegExp(`^${label}$`) }) })
const tap = async (label) => {
  await choice(label).first().click()
  await wait()
}

// 00 대기 화면
await kiosk.goto(BASE)
await wait()
await shot(kiosk, '00-idle')
check('대기 화면에 [주문 시작]', await kiosk.getByRole('button', { name: '주문 시작' }).isVisible())

await kiosk.getByRole('button', { name: '주문 시작' }).click()
await wait()
await shot(kiosk, '01-dine-option')
check('식사 장소 질문', (await bubble()).includes('포장'))

await tap('매장에서')
await shot(kiosk, '02-menu-recommend')
check('추천 메뉴 카드 3개', (await kiosk.locator('.menu-card').count()) === 3)

await kiosk.locator('.menu-card', { hasText: '빅맥' }).click()
await wait()
await shot(kiosk, '03a-option-set')
check('세트/단품 질문', (await bubble()).includes('세트로'))

await tap('세트')
await shot(kiosk, '03b-option-drink-1')
const page1 = await kiosk.locator('.choice').count()
check('음료 1쪽: 버튼 4개(음료 3 + 다른 음료 보기)', page1 === 4, `(${page1}개)`)
await tap('다른 음료 보기')
await shot(kiosk, '03b-option-drink-2')
check('음료 2쪽에 오렌지 주스 +700원', (await choice('오렌지 주스').innerText()).includes('+700원'))
check('음료 2쪽 돌아가기 버튼은 [처음 음료]', (await choice('처음 음료').count()) === 1)
await tap('처음 음료')
await tap('코카콜라 제로')
await shot(kiosk, '03c-option-size')
check('사이즈 질문', (await bubble()).includes('사이즈'))

await tap('라지')
check('장바구니에 담김', (await bubble()).includes('담았어요'))
await tap('주문할게요')
await shot(kiosk, '04-order-confirm')
check('주문 확인 8,000원', (await kiosk.locator('.cart-total').innerText()).includes('8,000원'))

await kiosk.getByRole('button', { name: '＋ 하나 더' }).click()
await wait()
check('[하나 더] → 16,000원', (await kiosk.locator('.cart-total').innerText()).includes('16,000원'))
await kiosk.getByRole('button', { name: '− 빼기' }).click()
await wait()
check('[빼기] → 8,000원', (await kiosk.locator('.cart-total').innerText()).includes('8,000원'))

// 사이드 바꾸기 (이슈 #13): 후렌치 후라이 → 맥너겟 4조각(+500원) → 다시 후렌치 후라이
check('확인 화면에 "사이드: 후렌치 후라이"', (await kiosk.locator('.cart-item__side').innerText()).includes('후렌치 후라이'))
await kiosk.getByRole('button', { name: '🔄 바꾸기' }).click()
await wait(400)
await shot(kiosk, '04b-side-change')
await kiosk.getByRole('button', { name: /맥너겟 4조각/ }).click()
await wait()
check('사이드 맥너겟으로 바꾸면 8,500원', (await kiosk.locator('.cart-total').innerText()).includes('8,500원'))
check('사이드 줄도 맥너겟으로 바뀜', (await kiosk.locator('.cart-item__side').innerText()).includes('맥너겟'))
await kiosk.getByRole('button', { name: '🔄 바꾸기' }).click()
await wait(400)
await kiosk.getByRole('button', { name: /후렌치 후라이/ }).click()
await wait()
check('다시 후렌치 후라이 → 8,000원', (await kiosk.locator('.cart-total').innerText()).includes('8,000원'))

await tap('맞아요')
await shot(kiosk, '05a-coupon-ask')
await tap('쿠폰 있어요')
await shot(kiosk, '05b-coupon-scan')

const scan = async (code) => {
  // 진짜 스캐너처럼 빠르게 타자 + Enter (연습용 입력칸이 아닌 화면에 직접)
  await kiosk.locator('.agent__text').click()
  await kiosk.keyboard.type(code, { delay: 5 })
  await kiosk.keyboard.press('Enter')
  await wait()
}
await scan('NOPE1234')
await shot(kiosk, 'e05-coupon-scan-fail')
check('바코드 못 읽음 안내', (await bubble()).includes('읽지 못했어요'))

await kiosk.locator('.practice input').fill('TEST0004')
await kiosk.getByRole('button', { name: '바코드 읽기' }).click()
await wait()
await shot(kiosk, 'e07-coupon-invalid')
check('기간 끝난 쿠폰 안내', (await bubble()).includes('기간이 끝난'))

await scan('TEST0001')
await shot(kiosk, '05c-coupon-applied')
check('쿠폰 할인 후 7,000원', (await kiosk.locator('.price-table').innerText()).includes('7,000원'))

await tap('카드 결제')
await shot(kiosk, '06b-payment-insert')
check('카드 꽂기 안내', (await bubble()).includes('꽂아'))

await kiosk.getByRole('button', { name: '결제 실패' }).click()
await kiosk.waitForTimeout(400)
await shot(kiosk, '06c-payment-processing')
await kiosk.waitForTimeout(1800)
await shot(kiosk, 'e09-payment-fail')
check('결제 실패 안내', (await bubble()).includes('결제가 안 됐어요'))

await tap('다시 결제할게요')
await kiosk.getByRole('button', { name: '결제 성공' }).click()
await kiosk.waitForTimeout(2500)
await shot(kiosk, '07-order-complete')
const number = (await kiosk.locator('.complete-screen__number').innerText()).trim()
check('주문번호 표시', /^\d+$/.test(number), `(${number}번)`)

// 매장 화면
const store = await browser.newPage({ viewport: { width: 960, height: 540 }, deviceScaleFactor: 2 })
await store.goto(`${BASE}/kitchen`)
await store.waitForTimeout(1500)
await store.screenshot({ path: `${OUT}/s02-kitchen-orders.jpg`, type: 'jpeg', quality: 80 })
const ticket = store.locator('.ticket', { hasText: `${number}번` })
check('주방 화면에 주문이 뜸', await ticket.isVisible())
await ticket.getByRole('button', { name: '완료' }).click()
await store.waitForTimeout(800)

await store.goto(`${BASE}/pickup`)
await store.waitForTimeout(1500)
await store.screenshot({ path: `${OUT}/s01-pickup-call.jpg`, type: 'jpeg', quality: 80 })
check('호출 화면 "가져가세요"에 번호', (await store.locator('.pickup__col--ready').innerText()).includes(number))

// 10초 뒤 처음 화면으로
await kiosk.waitForTimeout(9000)
check('주문 완료 10초 뒤 대기 화면', await kiosk.getByRole('button', { name: '주문 시작' }).isVisible())

// 직원 호출 + 주방 알림
await kiosk.getByRole('button', { name: '주문 시작' }).click()
await wait()
await kiosk.getByRole('button', { name: /직원 부르기/ }).click()
await wait()
await shot(kiosk, 'e04-staff-called')
check('직원 호출 안내 창', await kiosk.getByText('직원을 불렀어요').first().isVisible())
await store.goto(`${BASE}/kitchen`)
await store.waitForTimeout(1500)
await store.screenshot({ path: `${OUT}/s02-kitchen-staff-alert.jpg`, type: 'jpeg', quality: 80 })
check('주방 화면에 직원 호출 알림', await store.locator('.staff-alert').first().isVisible())
await kiosk.getByRole('button', { name: '괜찮아요, 계속할게요' }).click()
await wait()

// 메뉴판에서 직접 고르기
await tap('포장')
await tap('메뉴판 보기')
await shot(kiosk, '02b-menu-browser')
check('메뉴판 한 쪽에 4개', (await kiosk.locator('.browser .menu-card').count()) === 4)
await kiosk.locator('.browser .menu-card', { hasText: '불고기 버거' }).first().click()
await wait()
await tap('단품')
check('메뉴판에서 담기 (불고기 버거 2,500원)', (await bubble()).includes('불고기 버거') && (await kiosk.locator('.cart-summary').innerText()).includes('2,500원'))

// 결제 화면(카드 넣기 전)에서 손님이 떠남: 15초 → 도움 안내, 15초 더 → 대기 화면 (이슈 #14)
await tap('주문할게요')
await tap('맞아요')
await tap('없어요')
check('결제 화면까지 감', (await kiosk.locator('.progress__text').innerText()).includes('결제'))
// 안내 문장을 읽는 동안(마이크 표시 "말하는 중")은 타이머가 멈추므로, 읽기가 끝난 뒤부터 15초를 잰다
await kiosk.waitForFunction(() => !document.querySelector('.mic--speaking'), null, { timeout: 30000 })
await kiosk.waitForTimeout(15500)
await shot(kiosk, 'e02-need-help')
check('결제 화면 15초 무응답 → "도움이 필요하세요?"', await kiosk.getByText('도움이 필요하세요?').first().isVisible())
await kiosk.waitForTimeout(15500)
check('결제 화면 30초 무응답 → 대기 화면', await kiosk.getByRole('button', { name: '주문 시작' }).isVisible())

check('화면 오류(JS 에러) 없음', errors.length === 0, errors.join(' | '))
await browser.close()

const failed = results.filter((r) => !r.ok).length
log(`\n결과: ${results.length - failed} / ${results.length} 통과`)
process.exit(failed ? 1 : 0)
