import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { LANGS, usePoiStore } from '../stores/poiStore'
import { useUi } from '../stores/uiStore'
import { useAuth } from '../stores/authStore'
import { GeofenceEngine } from '../services/GeofenceEngine'
import { LocationService } from '../services/LocationService'
import { NarrationEngine } from '../services/NarrationEngine'
import { consentState, reportLocation, setConsent, track } from '../services/analytics'
import { buildPoiPopup } from '../services/poiPopup'
import PoiSearch from '../components/PoiSearch'
import FavoritesPanel from '../components/FavoritesPanel'
import { useFavorites } from '../stores/favoritesStore'

const MAP_CENTER = [106.7042, 10.7608] // tâm bản đồ ban đầu
const MAP_STYLE = {
  version: 8,
  sources: { osm: { type: 'raster', tiles: ['https://a.tile.openstreetmap.fr/osmfr/{z}/{x}/{y}.png', 'https://b.tile.openstreetmap.fr/osmfr/{z}/{x}/{y}.png'], tileSize: 256, attribution: '© OpenStreetMap contributors, tiles OSM France' } },
  layers: [{ id: 'osm', type: 'raster', source: 'osm' }],
}

function Splash({ onPick, t }) {
  return (
    <div className="splash" role="dialog" aria-label="Chọn ngôn ngữ">
      <h1>🍜 {t('app.title')}</h1>
      <p>Choose your language · Chọn ngôn ngữ</p>
      <div className="langs">{Object.entries(LANGS).map(([c, n]) => <button key={c} className="btn" onClick={() => onPick(c)}>{n}</button>)}</div>
    </div>
  )
}

export default function MapApp() {
  const { pois, lang, hasChosenLang, unreachable, load, setLang } = usePoiStore()
  const { t, status: uiStatus, strings: uiStrings } = useUi()
  const { user } = useAuth()
  const favoriteItems = useFavorites((s) => s.items)
  const favoritesLoading = useFavorites((s) => s.loading)
  const favoritesError = useFavorites((s) => s.error)
  const loadFavorites = useFavorites((s) => s.load)
  const toggleFavorite = useFavorites((s) => s.toggle)
  const [mock, setMock] = useState(false)
  const [current, setCurrent] = useState(null)
  const [tier, setTier] = useState(null)
  const [consent, setConsentState] = useState(consentState())
  const [area, setArea] = useState('')
  const mapEl = useRef(null)
  const map = useRef(null)
  const userMarker = useRef(null)
  const engine = useRef(null)
  const loc = useRef(null)
  const narrator = useRef(null)
  const poiMarkers = useRef(new Map())
  const [userPosition, setUserPosition] = useState(null)
  const favoriteIds = new Set(favoriteItems.map((poi) => poi.id))

  useEffect(() => { loadFavorites() }, [loadFavorites])

  // khu vực suy ra từ dữ liệu quán; tâm khu vực = trung bình toạ độ các quán trong khu
  const areas = useMemo(() => {
    const g = {}
    pois.forEach((p) => {
      if (!p.area) return
      const a = (g[p.area] ||= { name: p.area, lat: 0, lng: 0, n: 0 })
      a.lat += p.lat; a.lng += p.lng; a.n += 1
    })
    return Object.values(g).map((a) => ({ name: a.name, lat: a.lat / a.n, lng: a.lng / a.n })).sort((x, y) => x.name.localeCompare(y.name, 'vi'))
  }, [pois])

  const goArea = (name) => {
    setArea(name)
    const m = map.current
    if (!m) return
    if (!name) {
      const b = new maplibregl.LngLatBounds()
      pois.forEach((p) => b.extend([p.lng, p.lat]))
      if (!b.isEmpty()) m.fitBounds(b, { padding: 50, maxZoom: 14 })
      return
    }
    const a = areas.find((x) => x.name === name)
    if (a) m.flyTo({ center: [a.lng, a.lat], zoom: 16 })
  }

  // khởi động: nạp UI bundle + POI, delta sync định kỳ
  useEffect(() => {
    useUi.getState().load(usePoiStore.getState().lang)
    load()
    const timer = setInterval(() => load(), 60000)
    return () => clearInterval(timer)
  }, [load])

  useEffect(() => {
    map.current = new maplibregl.Map({ container: mapEl.current, style: MAP_STYLE, center: MAP_CENTER, zoom: 16 })
    narrator.current = new NarrationEngine({
      getLang: () => usePoiStore.getState().lang,
      onTier: setTier,
      onFinished: (poi) => { setCurrent(null); track('narration_played', { poi_id: poi.id, lang: usePoiStore.getState().lang }) },
    })
    engine.current = new GeofenceEngine({ onEnter: (poi) => { setCurrent(poi); narrator.current.narrate(poi) } })
    engine.current.start()
    loc.current = new LocationService((p) => {
      setUserPosition({ lat: p.lat, lng: p.lng })
      userMarker.current?.setLngLat([p.lng, p.lat])
      engine.current.checkGeofences(p)
      if (!loc.current.mock) reportLocation(p.lat, p.lng)
    })
    userMarker.current = new maplibregl.Marker({ color: '#1565c0' }).setLngLat(MAP_CENTER).addTo(map.current)
    loc.current.start()
    map.current.on('click', (e) => loc.current.pushMock(e.lngLat.lat, e.lngLat.lng))
    if (import.meta.env.DEV) window.__geo = { engine: engine.current, map: map.current }
    track('app_open')
    // bản đồ phải co giãn theo khung chứa (đổi cỡ cửa sổ, bố cục xong sau khi khởi tạo...)
    const ro = new ResizeObserver(() => map.current?.resize())
    ro.observe(mapEl.current)
    return () => { ro.disconnect(); narrator.current.stop(); engine.current.stop(); loc.current.stop(); map.current.remove() }
  }, [])

  useEffect(() => {
    engine.current?.setPois(pois)
    const m = map.current
    const listen = (poi) => { setCurrent(poi); narrator.current.narrate(poi); track('poi_viewed', { poi_id: poi.id, lang }) }
    const markers = pois.map((p) => {
      const { root, onOpen } = buildPoiPopup(p, {
        t, lang, onListen: listen,
        isFavorite: !user && favoriteIds.has(p.id),
        onFavorite: user ? undefined : toggleFavorite,
      })
      const popup = new maplibregl.Popup({ maxWidth: '320px', offset: 25 }).setDOMContent(root)
      popup.on('open', () => {
        // đưa marker xuống nửa dưới khung để popup (mở lên trên) không bị khuất dưới thanh tiêu đề
        m.easeTo({ center: [p.lng, p.lat], offset: [0, Math.min(220, m.getContainer().clientHeight * 0.3)], duration: 300 })
        onOpen()
      })
      const marker = new maplibregl.Marker({ color: p.is_fallback ? '#9e9e9e' : '#e65100' })
        .setLngLat([p.lng, p.lat]).setPopup(popup).addTo(m)
      poiMarkers.current.set(p.id, marker)
      return marker
    })
    return () => { markers.forEach((x) => x.remove()); poiMarkers.current.clear() }
  }, [pois, lang, t, uiStrings, favoriteItems, toggleFavorite, user])

  useEffect(() => { loc.current?.setMock(mock) }, [mock])

  const answer = (v) => { setConsent(v); setConsentState(v); if (v === 'granted') track('app_open') }
  const pickLang = (c) => { setLang(c); track('language_changed', { lang: c }) }

  return (
    <div className="app">
      <div className="bar">
        <strong>🍜 {t('app.title')}</strong>
        <label className="sr">{t('lang.label')}
          <select aria-label={t('lang.label')} value={lang} onChange={(e) => pickLang(e.target.value)}>
            {Object.entries(LANGS).map(([c, n]) => <option key={c} value={c}>{n}</option>)}</select></label>
        {areas.length > 1 && (
          <label>{t('area.label')}
            <select aria-label={t('area.label')} value={area} onChange={(e) => goArea(e.target.value)}>
              <option value="">{t('area.all')}</option>
              {areas.map((a) => <option key={a.name} value={a.name}>{a.name}</option>)}
            </select></label>)}
        <label><input type="checkbox" checked={mock} onChange={(e) => setMock(e.target.checked)} /> {t('mock.label')}</label>
        <span className="spacer" />
        {user ? <Link className="lnk" to={user.role === 'poi_owner' ? '/owner' : '/admin'}>{user.username}</Link>
          : <Link className="lnk" to="/login">{t('nav.login')}</Link>}
      </div>
      {unreachable && <div className="banner" role="status">⚠ {t('server.unreachable')}</div>}
      {uiStatus === 'pending' && <div className="banner info">{t('ready.partial')}</div>}
      <PoiSearch pois={pois} origin={userPosition} onSelect={(poi) => {
        map.current?.easeTo({ center: [poi.lng, poi.lat], zoom: Math.max(map.current.getZoom(), 17), duration: 450 })
        poiMarkers.current.get(poi.id)?.togglePopup()
      }} />
      {!user && <FavoritesPanel items={favoriteItems} loading={favoritesLoading}
        error={favoritesError} onSelect={(poi) => {
          map.current?.easeTo({ center: [poi.lng, poi.lat], zoom: Math.max(map.current.getZoom(), 17), duration: 450 })
          poiMarkers.current.get(poi.id)?.togglePopup()
        }} onRemove={toggleFavorite} />}
      <div className="map" ref={mapEl} />
      {current && <div className="toast" role="status">🎧 [Tier {tier}] {current.name}: {current.description}</div>}
      {consent === null && (
        <div className="consent" role="dialog"><span>{t('consent.text')}</span>
          <button className="btn" onClick={() => answer('granted')}>{t('consent.accept')}</button>
          <button className="btn ghost light" onClick={() => answer('declined')}>{t('consent.decline')}</button></div>)}
      {!hasChosenLang && <Splash onPick={pickLang} t={t} />}
    </div>
  )
}
