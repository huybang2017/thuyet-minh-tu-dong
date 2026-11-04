import distance from '@turf/distance'
import { point } from '@turf/helpers'

export const DEBOUNCE_MS = 3000
export const COOLDOWN_MS = 5 * 60 * 1000
export const RECONCILE_MS = 5000
export const DEFAULT_RADIUS_M = 30

/**
 * Phát hiện vào vùng POI: pendingEntries → debounce 3s → confirm ENTER,
 * chọn POI theo audio_priority rồi khoảng cách. Cooldown 5 phút sau khi trigger.
 */
export class GeofenceEngine {
  constructor({ onEnter, now = () => Date.now() } = {}) {
    this.onEnter = onEnter
    this.now = now
    this.pois = []
    this.pos = null
    this.pending = new Map() // poiId -> thời điểm bắt đầu vào vùng
    this.cooldown = new Map() // poiId -> thời điểm trigger
    this.timer = null
    this.debounceTimers = new Set()
  }

  setPois(pois) { this.pois = pois }

  start() {
    this.stop()
    this.timer = setInterval(() => this.reconcile(), RECONCILE_MS)
  }

  stop() {
    if (this.timer) clearInterval(this.timer)
    this.timer = null
    this.debounceTimers.forEach(clearTimeout)
    this.debounceTimers.clear()
  }

  distanceTo(poi) {
    return distance(point([this.pos.lng, this.pos.lat]), point([poi.lng, poi.lat]), { units: 'meters' })
  }

  checkGeofences(pos) {
    this.pos = pos
    const t = this.now()
    const inside = new Set()
    for (const poi of this.pois) {
      const d = this.distanceTo(poi)
      if (d <= (poi.trigger_radius ?? DEFAULT_RADIUS_M)) {
        inside.add(poi.id)
        if (!this.pending.has(poi.id)) {
          this.pending.set(poi.id, t)
          // xác nhận đúng lúc hết debounce thay vì chờ nhịp reconcile 5s kế tiếp
          const h = setTimeout(() => { this.debounceTimers.delete(h); this.reconcile() }, DEBOUNCE_MS + 50)
          this.debounceTimers.add(h)
        }
      }
    }
    for (const id of [...this.pending.keys()]) if (!inside.has(id)) this.pending.delete(id)
    this.reconcile()
  }

  reconcile() {
    if (!this.pos) return
    const t = this.now()
    const confirmed = []
    for (const [id, since] of this.pending) {
      if (t - since < DEBOUNCE_MS) continue
      if (t - (this.cooldown.get(id) ?? -Infinity) < COOLDOWN_MS) continue
      const poi = this.pois.find((p) => p.id === id)
      if (poi) confirmed.push({ poi, d: this.distanceTo(poi) })
    }
    if (!confirmed.length) return
    confirmed.sort((a, b) => (a.poi.audio_priority ?? 99) - (b.poi.audio_priority ?? 99) || a.d - b.d)
    const best = confirmed[0].poi
    this.cooldown.set(best.id, t)
    this.pending.delete(best.id)
    this.onEnter?.(best)
  }
}
