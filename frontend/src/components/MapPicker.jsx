/** Chọn tọa độ trực tiếp trên bản đồ (dùng maplibre đã có sẵn). Trả về {lat, lng}. */
import { useEffect, useRef } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { Modal } from './Common'

const MAP_STYLE = {
  version: 8,
  sources: { osm: { type: 'raster', tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'], tileSize: 256, attribution: '© OpenStreetMap' } },
  layers: [{ id: 'osm', type: 'raster', source: 'osm' }],
}

export function MapPicker({ open, onSelect, onClose, lat, lng }) {
  const mapRef = useRef(null)
  const containerRef = useRef(null)
  const markerRef = useRef(null)
  const startRef = useRef([106.7042, 10.7608])
  const selectRef = useRef(onSelect)
  selectRef.current = onSelect
  const la0 = Number(lat), lo0 = Number(lng)
  startRef.current = [Number.isFinite(lo0) && lng !== '' ? lo0 : 106.7042, Number.isFinite(la0) && lat !== '' ? la0 : 10.7608]

  useEffect(() => {
    if (!open || !containerRef.current) return
    const map = new maplibregl.Map({ container: containerRef.current, style: MAP_STYLE, center: startRef.current, zoom: 16 })
    mapRef.current = map
    markerRef.current = new maplibregl.Marker({ color: '#e65100', draggable: true })
      .setLngLat(startRef.current).addTo(map)
    map.on('click', (e) => {
      const { lat: la, lng: lo } = e.lngLat
      markerRef.current.setLngLat([lo, la])
      selectRef.current(la, lo)
    })
    markerRef.current.on('dragend', () => {
      const { lat: la, lng: lo } = markerRef.current.getLngLat()
      selectRef.current(la, lo)
    })
    // chờ div có kích thước rồi resize bản đồ
    setTimeout(() => map.resize(), 50)
    return () => { map.remove(); mapRef.current = null; markerRef.current = null }
  }, [open])

  return (
    <Modal open={open} title="Chọn điểm trên bản đồ" onClose={onClose}>
      <div ref={containerRef} style={{ width: '100%', height: '320px' }} />
      <p className="muted" style={{ marginTop: '.5rem', fontSize: '.8rem' }}>
        Bấm vào bản đồ hoặc kéo pin để chọn tọa độ quán.
      </p>
      <button type="button" className="btn" style={{ marginTop: '.5rem' }} onClick={onClose}>Xong</button>
    </Modal>
  )
}
