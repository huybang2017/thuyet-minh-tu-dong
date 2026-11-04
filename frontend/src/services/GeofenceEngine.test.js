import { describe, expect, it, vi } from 'vitest'
import { GeofenceEngine } from './GeofenceEngine'

const poi = (id, lat, lng, prio = 3) => ({ id, lat, lng, trigger_radius: 30, audio_priority: prio })

describe('GeofenceEngine', () => {
  it('chỉ trigger sau debounce 3s và không lặp trong cooldown', () => {
    let t = 0
    const entered = []
    const g = new GeofenceEngine({ now: () => t, onEnter: (p) => entered.push(p.id) })
    g.setPois([poi('a', 10.76, 106.70)])
    g.checkGeofences({ lat: 10.76, lng: 106.70 })
    expect(entered).toEqual([])
    t = 3100
    g.checkGeofences({ lat: 10.76, lng: 106.70 })
    expect(entered).toEqual(['a'])
    t = 10000
    g.checkGeofences({ lat: 10.76, lng: 106.70 })
    expect(entered).toEqual(['a'])
  })

  it('trigger ngay khi hết debounce, không chờ nhịp reconcile 5s', () => {
    vi.useFakeTimers()
    const entered = []
    const g = new GeofenceEngine({ onEnter: (p) => entered.push(p.id) })
    g.start()
    g.setPois([poi('a', 10.76, 106.70)])
    vi.advanceTimersByTime(1000) // lệch pha so với nhịp 5s
    g.checkGeofences({ lat: 10.76, lng: 106.70 })
    vi.advanceTimersByTime(3200)
    expect(entered).toEqual(['a']) // lúc này mới 4.2s, chưa tới tick 5s
    g.stop()
    vi.useRealTimers()
  })

  it('ra khỏi vùng trước debounce thì huỷ', () => {
    let t = 0
    const entered = []
    const g = new GeofenceEngine({ now: () => t, onEnter: (p) => entered.push(p.id) })
    g.setPois([poi('a', 10.76, 106.70)])
    g.checkGeofences({ lat: 10.76, lng: 106.70 })
    t = 1000
    g.checkGeofences({ lat: 10.77, lng: 106.71 })
    t = 4000
    g.checkGeofences({ lat: 10.77, lng: 106.71 })
    expect(entered).toEqual([])
  })

  it('ưu tiên audio_priority nhỏ hơn khi nhiều POI chồng nhau', () => {
    let t = 0
    const entered = []
    const g = new GeofenceEngine({ now: () => t, onEnter: (p) => entered.push(p.id) })
    g.setPois([poi('low', 10.76, 106.70, 5), poi('high', 10.76, 106.70, 1)])
    g.checkGeofences({ lat: 10.76, lng: 106.70 })
    t = 3100
    g.checkGeofences({ lat: 10.76, lng: 106.70 })
    expect(entered[0]).toBe('high')
  })
})
