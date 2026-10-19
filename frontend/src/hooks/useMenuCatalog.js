// 메뉴 정보 (사진·가격·옵션 추가 금액). 서버의 choices 는 글자뿐이라 이름으로 찾아서 붙인다.
import { useEffect, useState } from 'react'
import { kioskApi } from '../api/kiosk.js'

export function useMenuCatalog() {
  const [catalog, setCatalog] = useState({ menus: [], categories: [], byName: {}, optionPrice: {} })

  useEffect(() => {
    let alive = true
    ;(async () => {
      try {
        const [menus, categories] = await Promise.all([kioskApi.menus(), kioskApi.categories()])
        const byName = Object.fromEntries(menus.map((m) => [m.name, m]))
        // 세트 옵션(사이즈·음료·사이드)은 모든 세트 메뉴가 같아서 하나만 읽는다
        const setMenu = menus.find((m) => m.set_price != null)
        const detail = setMenu ? await kioskApi.menuDetail(setMenu.id) : { option_groups: [] }
        const optionPrice = {}
        detail.option_groups.forEach((g) => g.items.forEach((o) => (optionPrice[o.name] = o.extra_price)))
        if (alive) setCatalog({ menus, categories, byName, optionPrice })
      } catch {
        // 메뉴 정보를 못 읽어도 서버가 준 버튼 글자만으로 주문할 수 있다
      }
    })()
    return () => {
      alive = false
    }
  }, [])

  return catalog
}
