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

/** fetch thô (cookie + tự refresh 1 lần) — dùng cho upload nhị phân và tải file. */
async function rawFetch(path, init, retry = true) {
  const res = await fetch(path, { credentials: 'include', ...init })
  if (res.status === 401 && retry && await refresh()) return rawFetch(path, init, false)
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new ApiError(res.status, data.detail ?? data)
  }
  return res
}

export const MAX_IMAGE_BYTES = 2 * 1024 * 1024
export const IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp']

/** Tải một ảnh lên, trả về URL tĩnh (/static/images/…). */
export async function uploadImage(file) {
  if (!IMAGE_TYPES.includes(file.type)) throw new ApiError(415, 'Chỉ nhận ảnh JPEG, PNG hoặc WebP')
  if (file.size > MAX_IMAGE_BYTES) throw new ApiError(413, `Ảnh "${file.name}" vượt quá 2 MB`)
  const res = await rawFetch('/api/v1/media/images', { method: 'POST', headers: { 'Content-Type': file.type }, body: file })
  return (await res.json()).url
}

/** Tải file về máy (vd. CSV thống kê), lấy tên file từ Content-Disposition. */
export async function downloadFile(path, fallbackName = 'download') {
  const res = await rawFetch(path, { method: 'GET' })
  const name = /filename="?([^";]+)"?/.exec(res.headers.get('Content-Disposition') || '')?.[1] || fallbackName
  const url = URL.createObjectURL(await res.blob())
  const a = Object.assign(document.createElement('a'), { href: url, download: name })
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export const A = '/api/v1/admin'
