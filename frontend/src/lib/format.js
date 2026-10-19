export function won(amount) {
  return `${(amount ?? 0).toLocaleString('ko-KR')}원`
}

// 메뉴 그림 자리표시: 아직 메뉴 사진(image_url)이 없어서 종류별 그림 글자를 쓴다.
const CATEGORY_EMOJI = { 1: '🍔', 2: '🍟', 3: '🥤', 4: '🍦' }

export function menuEmoji(menu) {
  return CATEGORY_EMOJI[menu?.category_id] ?? '🍽️'
}
