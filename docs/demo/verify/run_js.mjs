import { readFileSync } from 'node:fs'
import { parse } from '../nlu.js'
import { catalog } from '../dialog.js'
const phrases = JSON.parse(readFileSync(new URL('./phrases.json', import.meta.url), 'utf8'))
const out = phrases.map((t) => { const p = parse(t, catalog); return { text: t, intent: p.intent, menus: p.menus.map((m) => [m.refId, m.isSet, m.quantity]), options: p.options.map((o) => o.refId), dine: p.dineType, set: p.setChoice, qd: p.qtyDelta, qa: p.qtyAbsolute, cat: p.category } })
console.log(JSON.stringify(out))
