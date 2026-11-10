import { useMemo, useState } from 'react'
import { searchPois } from '../services/poiSearch'

const RADII = [
  ['any', 'Mọi khoảng cách'],
  ['500', 'Trong 500 m'],
  ['1000', 'Trong 1 km'],
  ['3000', 'Trong 3 km'],
]

export default function PoiSearch({ pois, onSelect, origin }) {
  const [query, setQuery] = useState('')
  const [radius, setRadius] = useState('any')
  const [expanded, setExpanded] = useState(false)
  const results = useMemo(() => searchPois(pois, { query, radius, origin }), [pois, query, radius, origin])

  return (
    <section className="poi-search" aria-label="Tìm kiếm quán">
      <div className="poi-search-controls">
        <label className="poi-search-query">
          <span className="sr-only">Tìm quán theo tên, món ăn hoặc địa chỉ</span>
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Tìm quán, món ăn, địa chỉ…" />
        </label>
        <label className="poi-search-radius">
          <span className="sr-only">Lọc theo khoảng cách</span>
          <select value={radius} onChange={(event) => setRadius(event.target.value)}>
            {RADII.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <button className="poi-search-toggle" type="button" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>
          {expanded ? 'Ẩn' : `Danh sách (${results.length})`}
        </button>
      </div>
      {expanded && <div className="poi-search-results" role="list" aria-label="Kết quả tìm quán">
        {results.length ? results.map((poi) => (
          <button key={poi.id} type="button" role="listitem" className="poi-search-result" onClick={() => onSelect(poi)}>
            <strong>{poi.name}</strong>
            <span>{poi.address || poi.description}</span>
            {poi.distance !== null && <small>{poi.distance < 1000 ? `${Math.round(poi.distance)} m` : `${(poi.distance / 1000).toFixed(1)} km`}</small>}
          </button>
        )) : <p className="poi-search-empty">Không tìm thấy quán phù hợp.</p>}
      </div>}
    </section>
  )
}
