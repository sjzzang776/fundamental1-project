// 메뉴판 보기: 말 대신 메뉴판에서 직접 고르는 화면 (장바구니 API 사용)
// 접근성 규칙에 맞게 한 쪽에 메뉴 4개씩, 세트는 사이즈 → 음료를 한 번에 하나씩 묻는다.
import { useState } from 'react'
import { kioskApi } from '../api/kiosk.js'
import ChoiceList from '../components/ChoiceList.jsx'
import MenuCard from '../components/MenuCard.jsx'

const PER_PAGE = 4
// 손님에게 묻는 세트 옵션 순서. 나머지(세트 사이드)는 첫 번째(기본) 선택지로 담는다 (백엔드 대화와 같음)
const ASKED = ['세트 사이즈', '세트 음료']

export default function MenuBrowser({ catalog, onAdd, onClose }) {
  const [categoryId, setCategoryId] = useState(catalog.categories[0]?.id)
  const [page, setPage] = useState(0)
  const [picked, setPicked] = useState(null) // { detail, isSet, chosen: {groupName: item} }

  const menus = catalog.menus.filter((m) => m.category_id === categoryId)
  const pages = menus.length ? [] : [[]]
  for (let i = 0; i < menus.length; i += PER_PAGE) pages.push(menus.slice(i, i + PER_PAGE))
  const current = pages[Math.min(page, pages.length - 1)]

  const add = async (detail, isSet, chosen) => {
    const ids = isSet
      ? detail.option_groups.filter((g) => g.applies_to !== 'single').map((g) => (chosen[g.name] ?? g.items[0]).id)
      : []
    const ok = await onAdd({ menu_id: detail.id, quantity: 1, is_set: isSet, option_item_ids: ids })
    if (ok) onClose()
  }

  const pickMenu = async (menu) => {
    const detail = await kioskApi.menuDetail(menu.id).catch(() => null)
    if (!detail) return
    if (detail.set_price == null) return add(detail, false, {})
    setPicked({ detail, isSet: null, chosen: {} })
  }

  // 지금 물어볼 질문 (세트/단품 → 사이즈 → 음료)
  let question = null
  if (picked) {
    const { detail, isSet, chosen } = picked
    if (isSet === null) {
      question = {
        title: `${detail.name}, 세트로 드릴까요?`,
        choices: ['세트', '단품'],
        pick: (c) => (c === '단품' ? add(detail, false, {}) : setPicked({ ...picked, isSet: true })),
      }
    } else {
      const group = ASKED.map((n) => detail.option_groups.find((g) => g.name === n)).find((g) => g && !chosen[g.name])
      if (group) {
        question = {
          title: group.name === '세트 사이즈' ? '사이즈는 어떻게 드릴까요?' : '음료는 뭐로 드릴까요?',
          choices: group.items.map((o) => o.name),
          sub: Object.fromEntries(group.items.map((o) => [o.name, o.extra_price > 0 ? `+${o.extra_price.toLocaleString('ko-KR')}원` : undefined])),
          pick: (c) => {
            const next = { ...chosen, [group.name]: group.items.find((o) => o.name === c) }
            const left = ASKED.some((n) => detail.option_groups.find((g) => g.name === n) && !next[n])
            if (left) setPicked({ ...picked, chosen: next })
            else add(detail, true, next)
          },
        }
      }
    }
  }

  return (
    <div className="browser">
      <header className="browser__head">
        <h2>{question ? question.title : '메뉴판'}</h2>
        <button type="button" className="btn btn--secondary btn--small" onClick={picked ? () => setPicked(null) : onClose}>
          {picked ? '◀ 다시 고르기' : '✕ 닫기'}
        </button>
      </header>

      {question ? (
        <ChoiceList
          choices={question.choices}
          onChoose={question.pick}
          describe={(c) => ({ sub: question.sub?.[c] ?? (c === '세트' ? '감자튀김 + 음료' : undefined) })}
          moreLabel="다른 음료 보기"
          backLabel="처음 음료"
        />
      ) : (
        <>
          <div className="tabs" role="tablist">
            {catalog.categories.map((c) => (
              <button
                key={c.id}
                type="button"
                role="tab"
                aria-selected={c.id === categoryId}
                className={`tab ${c.id === categoryId ? 'tab--on' : ''}`}
                onClick={() => {
                  setCategoryId(c.id)
                  setPage(0)
                }}
              >
                {c.name}
              </button>
            ))}
          </div>
          <div className="menu-grid menu-grid--browser">
            {current.map((m) => (
              <MenuCard key={m.id} menu={m} onClick={() => pickMenu(m)} />
            ))}
          </div>
          {pages.length > 1 && (
            <div className="pager">
              <button type="button" className="btn btn--secondary" disabled={page === 0} onClick={() => setPage(page - 1)}>
                ◀ 앞 쪽
              </button>
              <span className="pager__text">
                {page + 1} / {pages.length}쪽
              </span>
              <button type="button" className="btn btn--secondary" disabled={page >= pages.length - 1} onClick={() => setPage(page + 1)}>
                다음 쪽 ▶
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
