// 바코드 스캐너는 키보드처럼 글자를 아주 빠르게 친 뒤 Enter를 누른다.
// 사람이 천천히 친 글자와 구분하려고, 글자 사이 간격이 maxGapMs 보다 길면 처음부터 다시 모은다.
export function createBarcodeReader({ onScan, maxGapMs = 100, minLength = 4 }) {
  let buffer = ''
  let last = 0

  return function handleKey(key, now = Date.now()) {
    if (now - last > maxGapMs) buffer = ''
    last = now
    if (key === 'Enter') {
      const code = buffer.trim()
      buffer = ''
      if (code.length >= minLength) {
        onScan(code)
        return true
      }
      return false
    }
    if (key.length === 1) buffer += key
    return false
  }
}
