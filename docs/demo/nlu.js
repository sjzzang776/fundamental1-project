// 손님 말 → 의도(intent)와 메뉴·옵션 찾기.
// backend/app/services/nlu.py 의 "규칙" 부분을 그대로 옮겼다 (LLM 다시 쓰기는 데모에 없음).
// 같은 문장에 파이썬과 같은 결과가 나오는지 docs/demo/verify/ 에서 대조한다.

const STRIP = /[\s.,!?~·'"()[\]+\-]/g
export const norm = (text) => text.replace(STRIP, '').toLowerCase()
const baseName = (name) => name.replace(/\s*\(.*?\)/g, '')
const has = (t, words) => words.some((w) => t.includes(w))

export class Catalog {
  // menus: [{id, name, aliases: [], ...}], options: [{id, name, groupId}], optionAliases: {name: [...]}
  constructor(menus, options, optionAliases) {
    this.menus = Object.fromEntries(menus.map((m) => [m.id, m]))
    this.options = Object.fromEntries(options.map((o) => [o.id, o]))
    const keys = new Set()
    for (const m of menus) for (const w of new Set([m.name, baseName(m.name), ...m.aliases])) keys.add(JSON.stringify([norm(w), m.id]))
    this.menuKeys = sortKeys(keys)
    const okeys = new Set()
    for (const o of options) for (const w of new Set([o.name, ...(optionAliases[o.name] || [])])) okeys.add(JSON.stringify([norm(w), o.id]))
    this.optionKeys = sortKeys(okeys)
  }
}

// 파이썬의 sorted(set(keys), key=-len) 와 같은 순서: 길이가 같으면 원래 순서가 정해지지 않으므로 (글자, id) 순으로 고정
function sortKeys(set) {
  return [...set].map((s) => JSON.parse(s)).sort((a, b) => b[0].length - a[0].length || (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : a[1] - b[1]))
}

function find(text, keys, kind) {
  const taken = new Array(text.length).fill(false)
  const found = []
  for (const [key, refId] of keys) {
    if (!key) continue
    let start = text.indexOf(key)
    while (start !== -1) {
      const end = start + key.length
      if (!taken.slice(start, end).some(Boolean)) {
        for (let i = start; i < end; i++) taken[i] = true
        found.push({ kind, refId, start, end, quantity: null, isSet: null })
      }
      start = text.indexOf(key, end)
    }
  }
  return found.sort((a, b) => a.start - b.start)
}

const QTY_WORDS = [['다섯', 5], ['여섯', 6], ['일곱', 7], ['여덟', 8], ['아홉', 9], ['하나', 1], ['한', 1], ['둘', 2], ['두', 2],
  ['셋', 3], ['세', 3], ['넷', 4], ['네', 4], ['열', 10]]
const NUM = '(\\d+|다섯|여섯|일곱|여덟|아홉|하나|한|둘|두|셋|세|넷|네|열)'

function numberAt(text) {
  const m = text.match(/^(\d+)/)
  if (m) return parseInt(m[1], 10)
  for (const [word, n] of QTY_WORDS) if (text.startsWith(word)) return n
  return null
}

const PARTICLES = ['으로', '이랑', '하고', '로', '도', '랑', '는', '은', '를', '을']

function readAfter(text, end) {
  let rest = text.slice(end, end + 12)
  let isSet = null
  let moved = true
  while (moved && rest) {
    moved = false
    if (rest.startsWith('세트')) { isSet = true; rest = rest.slice(2); moved = true }
    else if (rest.startsWith('단품')) { isSet = false; rest = rest.slice(2); moved = true }
    else {
      for (const p of PARTICLES) if (rest.startsWith(p)) { rest = rest.slice(p.length); moved = true; break }
    }
  }
  return [isSet, numberAt(rest)]
}

const DINE_IN_WORDS = ['먹고갈', '먹고가', '여기서', '매장', '안에서', '앉아서', '홀에서']
const TAKEOUT_WORDS = ['포장', '테이크아웃', 'takeout', '가져갈', '가져가', '가지고갈', '가지고가', '갖고갈', '갖고가', '들고갈', '들고가',
  '싸주', '싸줘', '싸가', '집에']
const REPEAT_WORDS = ['다시말해', '다시한번말해', '다시얘기', '다시읽어', '한번더말해', '뭐라고', '뭐라구', '뭐라는', '못들었', '못알아들']
const SLOWER_WORDS = ['천천히말', '천천히얘기', '천천히읽', '천천히좀', '너무빨라', '빨라요', '빠르다', '빨라서']
const FASTER_WORDS = ['빨리말', '빠르게말', '빨리읽', '말이느려', '너무느려', '느려요']
const LOUDER_WORDS = ['크게말', '크게얘기', '크게읽', '소리크게', '소리좀크게', '안들려', '잘안들', '소리가작']
const CLEAR_WORDS = ['다빼', '전부빼', '모두빼', '다지워', '전부지워', '싹지워', '모두지워', '비워', '다없애', '전부없애']
const WAIT_WORDS = ['잠깐만', '잠시만', '기다려', '생각좀', '생각해볼', '고민좀', '고민해볼', '천천히고를', '천천히볼']
const SMALLTALK_WORDS = ['안녕', '고마워', '고맙', '감사', '수고']
const PREV_WORDS = ['이전페이지', '이전쪽', '이전장', '앞쪽', '앞페이지', '앞장', '처음음료']
const UNDO_WORDS = ['잘못말', '잘못했', '잘못눌', '잘못들어', '잘못시켰', '잘못골랐', '전으로', '전단계', '뒤로', '되돌려', '되돌리',
  '돌아가', '돌아갈', '방금거취소', '방금거빼', '방금취소', '아까로', '무르', '물러']
const NEXT_WORDS = ['다음', '넘겨', '넘어가', '다른거', '다른것', '더보여', '더있', '다른음료', '다른메뉴', '다른햄버거', '다른버거',
  '다른디저트', '다른사이드', '딴거']
const SHOW_WORDS = ['메뉴판', '메뉴보여', '메뉴좀보여', '뭐있', '뭐가있', '종류', '보여줘', '보여주', '보여달', '볼래', '보고싶']
const CLOSE_WORDS = ['닫아', '닫기', '그만볼', '메뉴판그만', '안볼래']
const CATEGORY_WORDS = [['버거', ['햄버거', '버거']], ['사이드', ['사이드', '감자', '곁들']], ['음료', ['음료', '마실', '드링크', '음료수']],
  ['디저트', ['디저트', '후식', '아이스크림', '달달']]]

function screenIntent(t, p) {
  if (has(t, ['바꿔', '바꿀', '바꾸'])) return null
  const c = CATEGORY_WORDS.find(([, words]) => has(t, words))
  p.category = c ? c[0] : null
  if (has(t, REPEAT_WORDS)) return 'REPEAT'
  if (has(t, CLOSE_WORDS)) return 'CLOSE_MENU'
  if (has(t, PREV_WORDS)) return 'PAGE_PREV'
  if (has(t, NEXT_WORDS)) return 'PAGE_NEXT'
  if (has(t, ['메뉴판']) || (has(t, SHOW_WORDS) && (p.category || has(t, ['메뉴'])))) return 'SHOW_MENU'
  return null
}

function ruleIntent(t, p) {
  const hasM = p.menus.length > 0 || p.options.length > 0
  if (!t) return 'UNKNOWN'
  if (t.includes('직원')) return 'CALL_STAFF'
  if (has(t, ['처음으로', '처음부터', '처음화면'])) return 'RESTART'
  if (t.includes('말고') && hasM) return 'CHANGE_OPTION'
  if (p.options.length && has(t, ['바꿔', '바꾸', '변경'])) return 'CHANGE_OPTION'
  if (hasM && has(t, ['빼', '삭제', '없애', '지워'])) return 'REMOVE_ITEM'
  for (const [intent, words] of [['SPEAK_SLOWER', SLOWER_WORDS], ['SPEAK_FASTER', FASTER_WORDS], ['SPEAK_LOUDER', LOUDER_WORDS]]) {
    if (has(t, words) && !p.menus.length) return intent
  }
  if (!hasM) {
    for (const [intent, words] of [['CLEAR_CART', CLEAR_WORDS], ['UNDO', UNDO_WORDS]]) if (has(t, words)) return intent
    if (t.includes('얼마')) return 'TOTAL_PRICE'
    if (has(t, WAIT_WORDS)) return 'WAIT'
  }
  if (t.includes('취소') && !hasM) return 'CANCEL_ORDER'
  if (!hasM) {
    const screen = screenIntent(t, p)
    if (screen) return screen
  }
  if (has(t, ['추천', '뭐가맛있', '맛있는거', '뭐먹지', '골라줘', '인기'])) return 'RECOMMEND'
  if (p.menus.length && has(t, ['얼마', '칼로리', 'kcal', '알레르기', '매워', '매운가', '맵나', '뭐들어', '들어가', '들었', '뭐예요', '뭐에요'])) return 'ASK_MENU'
  if (has(t, ['뭐담', '장바구니', '주문내역', '뭐시켰', '뭐주문'])) return 'VIEW_CART'
  if (/더(줘|주세요|요|$)/.test(t)) {
    const m = t.match(new RegExp(NUM + '(개|잔)?더'))
    p.qtyDelta = m ? numberAt(m[1]) : 1
    return 'CHANGE_QTY'
  }
  if (hasM) {
    const m = t.match(new RegExp(NUM + '(개|잔)?(로|만)'))
    if (m) { p.qtyAbsolute = numberAt(m[1]); return 'CHANGE_QTY' }
    return 'ADD_ITEM'
  }
  if (has(t, ['아니', '아뇨', '싫어', '없어', '없이', '없습', '수정', '바꿀', '틀려'])) return 'DENY'
  if (['응', '네', '예', '맞아', '맞습', '좋아', '그래', '오케이', 'ok', '있어', '있습', '담아', '기본'].some((w) => t.startsWith(w)) ||
      has(t, ['쿠폰있', '다시결제', '다시할', '부탁', '맞아요'])) return 'CONFIRM'
  if (has(t, ['주문할게', '주문할께', '주문할래', '결제', '계산', '다골랐', '이대로', '이게다', '그게다', '주문완료'])) return 'CHECKOUT'
  if (p.setChoice !== null || p.dineType !== null) return 'ANSWER'
  if (has(t, ['주세요', '줘', '주문', '시킬', '먹을래', '먹고싶'])) return 'UNKNOWN_MENU'
  if (has(t, SMALLTALK_WORDS)) return 'SMALLTALK'
  return 'UNKNOWN'
}

export function parse(text, catalog) {
  const t = norm(text)
  const p = { text, intent: 'UNKNOWN', menus: [], options: [], dineType: null, setChoice: null, qtyDelta: null, qtyAbsolute: null, category: null }
  p.menus = find(t, catalog.menuKeys, 'menu')
  p.options = find(t, catalog.optionKeys, 'option')
  for (const m of p.menus) [m.isSet, m.quantity] = readAfter(t, m.end)
  if (has(t, DINE_IN_WORDS)) p.dineType = 'dine_in'
  else if (has(t, TAKEOUT_WORDS)) p.dineType = 'takeout'
  if (t.includes('세트')) p.setChoice = true
  else if (has(t, ['단품', '버거만', '그것만', '그거만'])) p.setChoice = false
  p.intent = ruleIntent(t, p)
  return p
}

export function similarMenu(text, catalog) {
  const t = norm(text)
  let best = null
  let bestScore = 0
  for (const [key, menuId] of catalog.menuKeys) {
    const score = [...new Set(key)].filter((ch) => t.includes(ch)).length
    if (score > bestScore && score >= 2) { best = catalog.menus[menuId]; bestScore = score }
  }
  return best
}
