// 주문 대화: backend/app/services/dialog.py 의 단계와 안내 문장을 브라우저용으로 줄여 옮겼다.
// 단계: DINE_TYPE → MENU → OPTION(세트?·음료·사이즈) → CONFIRM → PAYMENT → DONE  (데모에는 쿠폰 단계가 없다)
import { Catalog, norm, parse, similarMenu } from './nlu.js'
import { GROUPS, MENUS, OPTIONS, OPTION_ALIASES } from './data.js'

export const catalog = new Catalog(MENUS, OPTIONS, OPTION_ALIASES)
const ASKED_GROUPS = ['세트 음료', '세트 사이즈'] // 사이드는 묻지 않고 기본값(감자튀김) — 기획 결정 2026-10-19
const MSG_RETRY = '다시 한번 말씀해 주세요. 화면의 버튼을 눌러도 돼요.'

// ---------- 한국어 조사 ----------
function hasBatchim(word) {
  for (const ch of [...word].reverse()) {
    if (ch >= '가' && ch <= '힣') return (ch.charCodeAt(0) - 0xac00) % 28 !== 0
    if (/\d/.test(ch)) return '0136789'.includes(ch)
    if (/[a-zA-Z]/.test(ch)) return false
  }
  return false
}
const josa = (w, a, b) => w + (hasBatchim(w) ? a : b)
function ro(word) {
  for (const ch of [...word].reverse()) {
    if (ch >= '가' && ch <= '힣') { const f = (ch.charCodeAt(0) - 0xac00) % 28; return word + (f === 0 || f === 8 ? '로' : '으로') }
    if (/[0-9a-zA-Z]/.test(ch)) break
  }
  return word + '로'
}
export const won = (n) => `${n.toLocaleString('ko-KR')}원`
const COUNT = ['', '하나', '둘', '셋', '넷', '다섯', '여섯', '일곱', '여덟', '아홉', '열']
const countWord = (n) => (n <= 10 ? COUNT[n] : `${n}개`)

// ---------- 장바구니 ----------
const groupByName = (name) => GROUPS.findIndex(([g]) => g === name) + 1
const optionsOf = (groupId) => OPTIONS.filter((o) => o.groupId === groupId)
const defaultOption = (groupId) => optionsOf(groupId)[0]

export function itemLabel(item) {
  const menu = catalog.menus[item.menuId]
  if (!item.isSet) return menu.name
  const opts = ['세트 사이즈', '세트 사이드', '세트 음료'].map((g) => OPTIONS.find((o) => o.id === item.options[groupByName(g)])?.name).filter(Boolean)
  return `${baseName(menu.name)} 세트(${opts.join(', ')})`
}
const baseName = (n) => n.replace(/\s*\(.*?\)/g, '')
export function itemPrice(item) {
  const menu = catalog.menus[item.menuId]
  const unit = item.isSet ? menu.setPrice + Object.values(item.options).reduce((s, id) => s + OPTIONS.find((o) => o.id === id).extra, 0) : menu.price
  return unit * item.quantity
}

// ---------- 세션 ----------
export function newSession() {
  return { step: 'DINE_TYPE', dineType: null, cart: [], drafts: [], awaiting: null, returnToConfirm: false, orderNumber: null, nextId: 1 }
}
export const total = (s) => s.cart.reduce((a, i) => a + itemPrice(i), 0)
const itemsSentence = (s) => s.cart.map((i) => `${itemLabel(i)} ${countWord(i.quantity)}`).join(', ')

function draftNeed(d) {
  const menu = catalog.menus[d.menuId]
  if (menu.setPrice === null) d.isSet = false
  if (d.isSet === null) return ['SET', null]
  if (!d.isSet) return null
  for (const name of ASKED_GROUPS) {
    const g = groupByName(name)
    if (!(g in d.options)) return ['GROUP', g]
  }
  return null
}
const firstIncomplete = (s) => s.drafts.find((d) => draftNeed(d) !== null) || null

function question(d) {
  const menu = catalog.menus[d.menuId]
  const [need, g] = draftNeed(d)
  if (need === 'SET') return [`${josa(menu.name, '은', '는')} 세트로 드릴까요? 감자튀김과 음료가 같이 나와요.`, ['세트', '단품'], 'SET_OR_SINGLE']
  const [gname] = GROUPS[g - 1]
  const opts = optionsOf(g)
  if (gname === '세트 사이즈') return ['사이즈는 미디엄으로 드릴까요, 라지로 드릴까요? 라지는 800원 더 내요.', opts.map((o) => o.name), 'SET_SIZE']
  const label = gname.replace('세트 ', '')
  return [`${josa(label, '은', '는')} 뭐로 드릴까요? 기본은 ${josa(defaultOption(g).name, '이에요', '예요')}.`, opts.map((o) => o.name), 'SET_DRINK']
}

export function prompt(s) {
  if (s.step === 'OPTION') { const d = firstIncomplete(s); if (d) return question(d) }
  if (s.step === 'DINE_TYPE') return ['드시고 가세요, 포장하세요?', ['매장에서', '포장'], 'DINE_TYPE']
  if (s.step === 'CONFIRM') return [`${itemsSentence(s)}. 모두 ${won(total(s))}이에요. 맞으세요?`, ['맞아요', '수정할게요'], 'CONFIRM']
  if (s.step === 'PAYMENT') return [`${won(total(s))} 결제할게요. 카드를 화면 아래 빛나는 곳에 꽂아 주세요.`, ['카드 결제'], 'PAYMENT']
  if (s.step === 'DONE') {
    if (!s.orderNumber) return ['주문이 끝났어요. 새로 주문하시려면 처음 화면에서 [주문 시작]을 눌러 주세요.', [], 'CANCELLED']
    return [`주문번호는 ${s.orderNumber}번이에요. 화면에 번호가 뜨면 카운터에서 받아 가세요.`, [], 'DONE']
  }
  const rec = MENUS.filter((m) => m.recommended).map((m) => m.name)
  if (!s.cart.length) return ['어떤 걸 드시고 싶으세요? 고르기 어려우시면 추천해 드릴게요.', [...rec, '추천해 주세요'], 'MENU']
  return ["더 필요하신 건 있으세요? 다 고르셨으면 '주문할게요'라고 말씀해 주세요.", ['주문할게요', '추천해 주세요'], 'MENU_MORE']
}

function takeOptions(d, p, after = -1) {
  if (!d.isSet) return []
  const taken = []
  for (const opt of p.options) {
    if (opt.start < after) continue
    const o = catalog.options[opt.refId]
    if (o.groupId in d.options) continue
    d.options[o.groupId] = o.id
    p.menus = p.menus.filter((m) => !(m.start < opt.end && opt.start < m.end))
    taken.push(`${o.group.replace('세트 ', '')}는 ${ro(o.name)}`)
  }
  return taken
}
const mentionsSetOption = (d, p, after = -1) => catalog.menus[d.menuId].setPrice !== null && p.options.some((o) => o.start >= after)

function flushDrafts(s, notes) {
  let added = false
  s.drafts = s.drafts.filter((d) => {
    if (draftNeed(d) !== null) return true
    if (d.isSet) for (const [g] of GROUPS.map((x, i) => [i + 1])) if (!(g in d.options)) d.options[g] = defaultOption(g).id
    const item = { id: s.nextId++, menuId: d.menuId, quantity: d.quantity, isSet: !!d.isSet, options: d.isSet ? { ...d.options } : {} }
    const same = s.cart.find((i) => itemLabel(i) === itemLabel(item))
    if (same) same.quantity += item.quantity
    else s.cart.push(item)
    notes.push(`${itemLabel(item)} ${countWord(d.quantity)} 담았어요.`)
    added = true
    return false
  })
  return added
}

const cartItemFor = (s, menuIds) => [...s.cart].reverse().find((i) => menuIds.includes(i.menuId)) || null
const newDraft = (menu, quantity, isSet) => ({ menuId: menu.id, quantity: quantity || 1, isSet: menu.setPrice === null ? false : isSet, options: {} })

function applyEdit(s, p, notes) {
  let changed = false
  const touch = () => { if (!changed && ['CONFIRM', 'PAYMENT'].includes(s.step)) s.returnToConfirm = true; changed = true }
  if (p.intent === 'REMOVE_ITEM') {
    let removed = false
    for (const m of p.menus) {
      const item = cartItemFor(s, [m.refId])
      if (item) { touch(); s.cart = s.cart.filter((i) => i !== item); notes.push(`${josa(itemLabel(item), '을', '를')} 뺐어요.`); removed = true }
    }
    if (!removed) notes.push(p.options.length ? "세트 구성은 뺄 수 없어요. 다른 것으로 바꿔 드릴까요? 예: '콜라 말고 사이다'" : '장바구니에 그 메뉴가 없어요.')
    return changed
  }
  if (p.intent === 'CHANGE_OPTION' && !norm(p.text).includes('말고')) {
    const latest = {}
    for (const o of p.options) latest[catalog.options[o.refId].groupId] = catalog.options[o.refId]
    for (const opt of Object.values(latest)) {
      const item = [...s.cart].reverse().find((i) => i.isSet)
      if (!item) continue
      if (item.options[opt.groupId] === opt.id) { notes.push(`이미 ${josa(opt.name, '이에요', '예요')}.`); continue }
      touch(); item.options[opt.groupId] = opt.id
      notes.push(`${josa(opt.group.replace('세트 ', ''), '을', '를')} ${ro(opt.name)} 바꿨어요.`)
    }
    if (!changed && !notes.length) notes.push("바꿀 세트가 없어요. 예: '사이드 너겟으로 바꿔 주세요'")
    return changed
  }
  if (p.intent === 'CHANGE_OPTION') { // "A 말고 B"
    const cut = norm(p.text).indexOf('말고')
    const before = p.options.filter((m) => m.end <= cut)
    const after = p.options.filter((m) => m.start >= cut)
    if (before.length && after.length) {
      const oldO = catalog.options[before.at(-1).refId]
      const newO = catalog.options[after[0].refId]
      const item = [...s.cart].reverse().find((i) => i.options[oldO.groupId] === oldO.id)
      if (item && oldO.groupId === newO.groupId) {
        touch(); item.options[newO.groupId] = newO.id
        notes.push(`${josa(oldO.name, '을', '를')} ${ro(newO.name)} 바꿨어요.`)
        return true
      }
    }
    const bm = p.menus.filter((m) => m.end <= cut)
    const am = p.menus.filter((m) => m.start >= cut)
    if (bm.length && am.length) {
      const item = cartItemFor(s, [bm.at(-1).refId])
      const nm = catalog.menus[am[0].refId]
      if (item) {
        touch(); s.cart = s.cart.filter((i) => i !== item)
        s.drafts.push(newDraft(nm, item.quantity, nm.setPrice ? item.isSet : false))
        notes.push(`${josa(itemLabel(item), '을', '를')} 뺐어요.`)
        return true
      }
    }
    notes.push("무엇을 무엇으로 바꿀지 다시 말씀해 주세요. 예: '콜라 말고 사이다'")
    return changed
  }
  if (p.intent === 'CHANGE_QTY') {
    const item = p.menus.length ? cartItemFor(s, p.menus.map((m) => m.refId)) : s.cart.at(-1) || null
    if (!item && p.menus.length) { p.intent = 'ADD_ITEM'; for (const m of p.menus) m.quantity = p.qtyAbsolute || m.quantity }
    else if (!item) { notes.push('장바구니가 비어 있어요.'); return changed }
    else {
      touch()
      item.quantity = p.qtyDelta ? item.quantity + p.qtyDelta : p.qtyAbsolute || item.quantity
      notes.push(`${josa(itemLabel(item), '을', '를')} ${ro(countWord(item.quantity))} 바꿨어요.`)
      return true
    }
  }
  if (p.intent === 'ADD_ITEM') {
    for (const m of [...p.menus]) {
      if (!p.menus.includes(m)) continue
      const menu = catalog.menus[m.refId]
      touch()
      const isSet = m.isSet !== null ? m.isSet : p.menus.length === 1 ? p.setChoice : null
      const d = newDraft(menu, m.quantity, isSet)
      if (d.isSet === null && mentionsSetOption(d, p, m.end)) d.isSet = true
      if (d.isSet) takeOptions(d, p, m.end)
      s.drafts.push(d)
    }
    if (!p.menus.length && p.options.length) notes.push(MSG_RETRY)
  }
  return changed
}

function answerOption(d, p) {
  const need = draftNeed(d)
  let answered = false
  if (need && need[0] === 'SET') {
    if (p.setChoice !== null) d.isSet = p.setChoice
    else if (p.intent === 'CONFIRM') d.isSet = true
    else if (p.intent === 'DENY') d.isSet = false
    else if (mentionsSetOption(d, p)) d.isSet = true
    else return [false, []]
    answered = true
  }
  const taken = d.isSet ? takeOptions(d, p) : []
  if (taken.length) answered = true
  else if (need && need[0] === 'GROUP' && p.intent === 'CONFIRM') { d.options[need[1]] = defaultOption(need[1]).id; answered = true }
  return [answered, taken]
}

function menuInfo(menu) {
  let t = `${josa(menu.name, '은', '는')} 단품 ${won(menu.price)}`
  if (menu.setPrice) t += `, 세트 ${won(menu.setPrice)}`
  return t + '이에요.'
}

function undo(s, notes) {
  const d = firstIncomplete(s)
  if (s.step === 'OPTION' || d) {
    if (d) { s.drafts = s.drafts.filter((x) => x !== d); notes.push(`${josa(catalog.menus[d.menuId].name, '은', '는')} 담지 않을게요.`) }
    const back = s.returnToConfirm && s.cart.length
    s.returnToConfirm = false
    s.step = back ? 'CONFIRM' : 'MENU'
    return null
  }
  if (s.step === 'MENU') {
    if (s.cart.length) { const item = s.cart.pop(); notes.push(`방금 담은 ${josa(itemLabel(item), '을', '를')} 뺐어요.`); return null }
    s.dineType = null; s.step = 'DINE_TYPE'; notes.push('식사 장소부터 다시 고를게요.'); return null
  }
  if (s.step === 'CONFIRM') { s.returnToConfirm = true; s.step = 'MENU'; return ["어떤 걸 바꿔 드릴까요? 예: '콜라 빼줘', '하나 더'", ['주문할게요'], 'EDIT'] }
  if (s.step === 'PAYMENT') { s.step = 'CONFIRM'; notes.push('주문 확인으로 돌아갈게요.'); return null }
  notes.push('지금이 처음 단계예요.')
  return null
}

// 말 한 번 처리 → { reply, choices, question, intent, actions }
export function handle(s, text) {
  const p = parse(text, catalog)
  const notes = []
  const actions = []
  let override = null
  const reply = (ov = override) => {
    const [t, choices, q] = ov || prompt(s)
    return { reply: [...notes, t].join(' ').trim(), choices, question: q, intent: p.intent, actions }
  }
  if (s.step === 'DONE') return reply()
  if (p.intent === 'CALL_STAFF') { notes.push('직원을 불렀어요. 잠시만 기다려 주세요.'); actions.push('staff'); return reply() }
  if (p.intent === 'RESTART') { Object.assign(s, newSession(), { nextId: s.nextId }); notes.push('처음부터 다시 할게요.'); return reply() }
  if (s.awaiting === 'CANCEL_CONFIRM') {
    s.awaiting = null
    if (['CONFIRM', 'CANCEL_ORDER'].includes(p.intent)) { s.cart = []; s.drafts = []; s.step = 'DONE'; return reply(['주문을 취소했어요. 이용해 주셔서 고마워요.', [], 'CANCELLED']) }
    if (p.intent === 'DENY') { notes.push('계속 주문할게요.'); return reply() }
  }
  if (p.intent === 'CANCEL_ORDER') { s.awaiting = 'CANCEL_CONFIRM'; return reply(['주문을 취소할까요? 담은 메뉴가 모두 지워져요.', ['네, 취소할게요', '아니요'], 'CANCEL_CONFIRM']) }
  if (['SPEAK_SLOWER', 'SPEAK_FASTER', 'SPEAK_LOUDER'].includes(p.intent)) {
    const speed = { SPEAK_SLOWER: 'slower', SPEAK_FASTER: 'faster', SPEAK_LOUDER: 'louder' }[p.intent]
    actions.push(`voice:${speed}`)
    notes.push({ slower: '네, 천천히 말씀드릴게요.', faster: '네, 조금 빠르게 말씀드릴게요.', louder: '네, 크게 말씀드릴게요.' }[speed])
    return reply()
  }
  if (p.intent === 'TOTAL_PRICE') { notes.push(s.cart.length ? `지금 ${itemsSentence(s)}, 모두 ${won(total(s))}이에요.` : '아직 담긴 메뉴가 없어요.'); return reply() }
  if (p.intent === 'CLEAR_CART' && s.step !== 'DINE_TYPE') { s.cart = []; s.drafts = []; s.awaiting = null; s.step = 'MENU'; notes.push('장바구니를 모두 비웠어요.'); return reply() }
  if (p.intent === 'WAIT') { const [, c, q] = prompt(s); return reply(['네, 천천히 고르세요. 다 고르시면 말씀해 주세요.', c, q]) }
  if (p.intent === 'SMALLTALK') { notes.push(['고마', '감사', '수고'].some((w) => text.includes(w)) ? '네, 고마워요!' : '네, 안녕하세요!'); return reply() }
  if (p.intent === 'UNDO') return reply(undo(s, notes))
  if (p.intent === 'REPEAT') return reply()
  if (p.intent === 'SHOW_MENU' || (p.intent === 'PAGE_NEXT' && s.step === 'MENU')) {
    if (s.step !== 'MENU') { const [t, c, q] = prompt(s); return reply([`메뉴판은 메뉴를 고를 때 볼 수 있어요. ${t}`, c, q]) }
    actions.push(`menu:${p.category || ''}`)
    const [, c, q] = prompt(s)
    return reply([`${p.category ? `${p.category} 메뉴를` : '메뉴판을'} 보여 드릴게요. 화면에서 고르시거나 이름을 말씀해 주세요.`, c, q])
  }
  if (p.intent === 'CLOSE_MENU') { actions.push('menu:close'); return reply() }
  if (['PAGE_NEXT', 'PAGE_PREV'].includes(p.intent)) { actions.push(p.intent === 'PAGE_NEXT' ? 'page:next' : 'page:prev'); return reply() }

  if (p.dineType && s.step !== 'DONE') s.dineType = p.dineType

  if (s.step === 'PAYMENT' && ['CONFIRM', 'CHECKOUT', 'ANSWER'].includes(p.intent)) { actions.push('pay'); return reply() }
  if (s.step === 'PAYMENT' && p.intent === 'DENY') { s.returnToConfirm = true; s.step = 'MENU'; return reply(['어떤 걸 바꿔 드릴까요?', ['주문할게요'], 'EDIT']) }
  if (s.step === 'CONFIRM' && ['CONFIRM', 'CHECKOUT'].includes(p.intent)) { s.step = 'PAYMENT'; return reply() }
  if (s.step === 'CONFIRM' && p.intent === 'DENY') { s.returnToConfirm = true; s.step = 'MENU'; return reply(["어떤 걸 바꿔 드릴까요? 예: '콜라 빼줘', '하나 더'", ['주문할게요'], 'EDIT']) }

  let answered = false
  const d = firstIncomplete(s)
  if (d) {
    const [a, taken] = answerOption(d, p)
    answered = a
    if (answered && (['CONFIRM', 'DENY', 'ANSWER', 'UNKNOWN'].includes(p.intent) || !p.menus.length)) p.intent = 'ANSWER'
    if (taken.length && draftNeed(d) !== null) notes.push(`${taken.join(', ')} 할게요.`)
  }
  const changed = applyEdit(s, p, notes)

  if (p.intent === 'RECOMMEND') {
    const rec = MENUS.filter((m) => m.recommended)
    notes.push(`제가 추천하는 메뉴는 ${rec.map((m) => m.name).join(', ')}예요. 어떤 걸로 드릴까요?`)
    if (s.step === 'DINE_TYPE' && s.dineType) s.step = 'MENU'
    override = [notes.join(' '), rec.map((m) => m.name), 'RECOMMEND']
    notes.length = 0
  } else if (p.intent === 'ASK_MENU') notes.push(p.menus.map((m) => menuInfo(catalog.menus[m.refId])).join(' '))
  else if (p.intent === 'VIEW_CART') notes.push(s.cart.length ? `지금 ${josa(itemsSentence(s), '이', '가')} 담겨 있어요.` : '아직 담긴 메뉴가 없어요.')
  else if (p.intent === 'UNKNOWN_MENU') {
    const sim = similarMenu(text, catalog)
    notes.push(sim ? `그 메뉴는 없어요. 비슷한 ${josa(sim.name, '은', '는')} 어떠세요?` : '그 메뉴는 없어요.')
    if (sim) { override = [notes.join(' '), [sim.name, '추천해 주세요'], 'SIMILAR_MENU']; notes.length = 0 }
  } else if (p.intent === 'UNKNOWN' && !answered && !(p.dineType && s.step === 'DINE_TYPE')) notes.push(MSG_RETRY)

  const added = flushDrafts(s, notes)
  let wantConfirm = p.intent === 'CHECKOUT'
  if (wantConfirm && !s.cart.length && !s.drafts.length) { notes.push('아직 담긴 메뉴가 없어요.'); wantConfirm = false }

  if (firstIncomplete(s)) s.step = 'OPTION'
  else if (s.dineType === null) s.step = 'DINE_TYPE'
  else if (s.cart.length && (wantConfirm || (s.returnToConfirm && (changed || added || answered)))) { s.step = 'CONFIRM'; s.returnToConfirm = false }
  else if (['DINE_TYPE', 'OPTION'].includes(s.step) || (s.step === 'CONFIRM' && !s.cart.length)) s.step = 'MENU'
  if (override && s.step === 'OPTION') override = null
  return reply()
}

// 버튼으로 결제 (데모: 실제 카드 단말 대신 1.5초 기다림)
export function pay(s) {
  s.orderNumber = 100 + Math.floor(Math.random() * 900)
  s.step = 'DONE'
  return { reply: prompt(s)[0], choices: [], question: 'DONE', intent: 'PAY', actions: [] }
}
