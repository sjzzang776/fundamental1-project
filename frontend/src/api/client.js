// 서버와 이야기하는 공통 함수. 에러는 노션 API 명세 형식 {"error": {"code", "message", "detail"}} 를 따른다.
export class ApiError extends Error {
  constructor(status, code, message, detail = {}) {
    super(message)
    this.status = status
    this.code = code
    this.detail = detail
  }
}

export async function request(path, { method = 'GET', body, headers = {}, form } = {}) {
  const options = { method, headers: { ...headers } }
  if (form) {
    options.body = form
  } else if (body !== undefined) {
    options.headers['Content-Type'] = 'application/json'
    options.body = JSON.stringify(body)
  }

  let res
  try {
    res = await fetch(path, options)
  } catch {
    throw new ApiError(0, 'NETWORK_ERROR', '서버와 연결이 잠깐 끊겼어요')
  }
  if (res.status === 204) return null
  const data = await res.json().catch(() => null)
  if (!res.ok) {
    const err = data?.error
    throw new ApiError(res.status, err?.code ?? 'UNKNOWN', err?.message ?? `요청 실패 (${res.status})`, err?.detail)
  }
  return data
}
