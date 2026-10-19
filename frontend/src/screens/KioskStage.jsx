// 키오스크 화면(Figma 크기 그대로)을 브라우저 창 크기에 맞게 줄이거나 늘려서 보여 준다.
// 기본은 세로형 1080 × 1920, 매장 화면(호출·주방)은 가로형 1920 × 1080.
import { useEffect, useState } from 'react'

export default function KioskStage({ children, width = 1080, height = 1920 }) {
  const fit = () => Math.min(window.innerWidth / width, window.innerHeight / height)
  const [scale, setScale] = useState(fit)
  useEffect(() => {
    const onResize = () => setScale(fit())
    onResize()
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [width, height])

  return (
    <div className="stage-wrap">
      <div className="stage" style={{ width, height, transform: `scale(${scale})` }}>
        {children}
      </div>
    </div>
  )
}
