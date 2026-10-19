// 주소로 화면을 나눈다: / 손님 키오스크, /pickup 호출 화면, /kitchen 주방 화면
import Kiosk from './screens/Kiosk.jsx'
import KitchenOrders from './store-screens/KitchenOrders.jsx'
import PickupBoard from './store-screens/PickupBoard.jsx'

export default function App() {
  const path = window.location.pathname.replace(/\/+$/, '')
  if (path === '/pickup') return <PickupBoard />
  if (path === '/kitchen') return <KitchenOrders />
  return <Kiosk />
}
