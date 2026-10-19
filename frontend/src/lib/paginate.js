// 기획서 접근성 규칙: 한 화면에 고를 수 있는 버튼은 최대 4개.
// 4개 이하면 한 쪽에 모두, 5개 이상이면 한 쪽에 3개 + [다른 것 보기]/[앞으로] 버튼을 둔다.
export const MAX_PER_PAGE = 4

export function paginate(items, max = MAX_PER_PAGE) {
  if (items.length <= max) return [items]
  const size = max - 1
  const pages = []
  for (let i = 0; i < items.length; i += size) pages.push(items.slice(i, i + size))
  return pages
}
