/** Consent-gated analytics: chỉ gửi khi user đã đồng ý. Runtime location là lane riêng, chỉ ô lưới ~110m. */
const get = (k) => { try { return localStorage.getItem(k) } catch { return null } }
const set = (k, v) => { try { localStorage.setItem(k, v) } catch { /* ignore */ } }

export const consentState = () => get('analytics_consent') // 'granted' | 'declined' | null
export const setConsent = (v) => set('analytics_consent', v)

function deviceId() {
  let id = get('device_id')
  if (!id) { id = 'd' + crypto.randomUUID().replaceAll('-', ''); set('device_id', id) }
  return id
}
const sessionId = 's' + Math.random().toString(36).slice(2, 12)

export function track(event, extra = {}) {
  if (consentState() !== 'granted' || !navigator.onLine) return
  fetch('/api/v1/analytics/collect', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, keepalive: true,
    body: JSON.stringify({ consent: true, device_id: deviceId(), session_id: sessionId, event, ...extra }),
  }).catch(() => {})
}

let lastLoc = 0
export function reportLocation(lat, lng) {
  if (Date.now() - lastLoc < 60000 || !navigator.onLine) return
  lastLoc = Date.now()
  fetch('/api/v1/runtime/location', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ lat, lng }),
  }).catch(() => {})
}
