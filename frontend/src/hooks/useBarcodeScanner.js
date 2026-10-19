// 키오스크 바코드 스캐너 입력 받기 (enabled 일 때만)
import { useEffect, useRef } from 'react'
import { createBarcodeReader } from '../lib/barcode.js'

export function useBarcodeScanner(enabled, onScan) {
  const onScanRef = useRef(onScan)
  onScanRef.current = onScan

  useEffect(() => {
    if (!enabled) return undefined
    const read = createBarcodeReader({ onScan: (code) => onScanRef.current(code) })
    const onKey = (e) => {
      if (e.target instanceof HTMLInputElement) return // 연습용 입력칸은 따로 처리
      if (read(e.key)) e.preventDefault()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [enabled])
}
