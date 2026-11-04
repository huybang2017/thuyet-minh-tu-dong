export const GPS_THROTTLE_MS = 5000

/** watchPosition có throttle 5s; hỗ trợ mock GPS cho dev. */
export class LocationService {
  constructor(onPosition) {
    this.onPosition = onPosition
    this.watchId = null
    this.last = 0
    this.mock = false
  }

  start() {
    if (!navigator.geolocation) return
    this.watchId = navigator.geolocation.watchPosition(
      (p) => {
        if (this.mock) return
        const now = Date.now()
        if (now - this.last < GPS_THROTTLE_MS) return
        this.last = now
        this.onPosition({ lat: p.coords.latitude, lng: p.coords.longitude, accuracy: p.coords.accuracy })
      },
      () => {},
      { enableHighAccuracy: true, maximumAge: 30000, timeout: 15000 },
    )
  }

  setMock(enabled) { this.mock = enabled }

  pushMock(lat, lng) { if (this.mock) this.onPosition({ lat, lng, accuracy: 5 }) }

  stop() { if (this.watchId != null) navigator.geolocation.clearWatch(this.watchId) }
}
