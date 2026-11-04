import { useEffect, useRef, useState } from 'react'
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

const MAP_CENTER = [106.7042, 10.7608] // tâm bản đồ ban đầu
const MAP_STYLE = {
  version: 8,
  sources: { osm: { type: 'raster', tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'], tileSize: 256, attribution: '© OpenStreetMap' } },
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
  const { t, status: uiStatus } = useUi()
  const { user } = useAuth()
  const [mock, setMock] = useState(false)
  const [current, setCurrent] = useState(null)
  const [tier, setTier] = useState(null)
  const [consent, setConsentState] = useState(consentState())
  const mapEl = useRef(null)
  const map = useRef(null)
  const userMarker = useRef(null)
  const engine = useRef(null)
  const loc = useRef(null)
  const narrator = useRef(null)

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
      userMarker.current?.setLngLat([p.lng, p.lat])
      engine.current.checkGeofences(p)
      if (!loc.current.mock) reportLocation(p.lat, p.lng)
    })
    userMarker.current = new maplibregl.Marker({ color: '#1565c0' }).setLngLat(MAP_CENTER).addTo(map.current)
    loc.current.start()
    map.current.on('click', (e) => loc.current.pushMock(e.lngLat.lat, e.lngLat.lng))
    if (import.meta.env.DEV) window.__geo = { engine: engine.current, map: map.current }
    track('app_open')
    return () => { narrator.current.stop(); engine.current.stop(); loc.current.stop(); map.current.remove() }
  }, [])

  useEffect(() => {
    engine.current?.setPois(pois)
    const m = map.current
    const markers = pois.map((p) => new maplibregl.Marker({ color: p.is_fallback ? '#9e9e9e' : '#e65100' })
      .setLngLat([p.lng, p.lat])
      .setPopup(new maplibregl.Popup().setHTML(`<b>${p.name}</b><br/>${p.description}`)).addTo(m))
    return () => markers.forEach((x) => x.remove())
  }, [pois])

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
        <label><input type="checkbox" checked={mock} onChange={(e) => setMock(e.target.checked)} /> {t('mock.label')}</label>
        <span className="spacer" />
        {user ? <Link className="lnk" to={user.role === 'poi_owner' ? '/owner' : '/admin'}>{user.username}</Link>
          : <Link className="lnk" to="/login">{t('nav.login')}</Link>}
      </div>
      {unreachable && <div className="banner" role="status">⚠ {t('server.unreachable')}</div>}
      {uiStatus === 'pending' && <div className="banner info">{t('ready.partial')}</div>}
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
