/** fetch wrapper: cookie httpOnly + tự refresh 1 lần khi 401. */
export class ApiError extends Error {
  constructor(status, detail) {
    super(typeof detail === 'string' ? detail : detail?.message || `HTTP ${status}`)
    this.status = status
    this.detail = detail
  }
}

let refreshing = null
async function refresh() {
  refreshing ||= fetch('/api/v1/admin/auth/refresh', { method: 'POST', credentials: 'include' })
    .then((r) => r.ok).finally(() => { refreshing = null })
  return refreshing
}

export async function api(path, { method = 'GET', body, retry = true } = {}) {
  const res = await fetch(path, {
    method, credentials: 'include',
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (res.status === 401 && retry && !path.includes('/auth/')) {
    if (await refresh()) return api(path, { method, body, retry: false })
  }
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new ApiError(res.status, data.detail ?? data)
  return data
}

export const A = '/api/v1/admin'
