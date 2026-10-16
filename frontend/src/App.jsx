import { useState } from 'react'

async function callApi(path, options) {
  const res = await fetch(path, options)
  const body = await res.json().catch(() => null)
  if (!res.ok) {
    throw new Error(body?.detail || `요청 실패 (${res.status})`)
  }
  return body
}

export default function App() {
  const [health, setHealth] = useState(null)
  const [healthError, setHealthError] = useState('')
  const [text, setText] = useState('')
  const [prediction, setPrediction] = useState(null)
  const [predictError, setPredictError] = useState('')
  const [loading, setLoading] = useState(false)

  async function checkHealth() {
    setHealthError('')
    setHealth(null)
    try {
      setHealth(await callApi('/api/health'))
    } catch (e) {
      setHealthError(e.message)
    }
  }

  async function runPredict(e) {
    e.preventDefault()
    setPredictError('')
    setPrediction(null)
    setLoading(true)
    try {
      setPrediction(
        await callApi('/api/predict', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text }),
        }),
      )
    } catch (e) {
      setPredictError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="container">
      <h1>Fundamental 1 project</h1>

      <section className="card">
        <h2>백엔드 연결 테스트</h2>
        <button onClick={checkHealth}>백엔드 연결 테스트</button>
        {health && <pre className="result">{JSON.stringify(health, null, 2)}</pre>}
        {healthError && <p className="error">{healthError}</p>}
      </section>

      <section className="card">
        <h2>모델 테스트</h2>
        <form onSubmit={runPredict} className="row">
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="모델에 보낼 문장을 입력하세요"
          />
          <button type="submit" disabled={loading || !text.trim()}>
            {loading ? '요청 중…' : '모델 테스트'}
          </button>
        </form>
        {prediction && <pre className="result">{JSON.stringify(prediction, null, 2)}</pre>}
        {predictError && <p className="error">{predictError}</p>}
      </section>
    </main>
  )
}
