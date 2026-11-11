import { useState } from 'react'
export default function FavoritesPanel({ items, loading, error, onSelect, onRemove }) {
  const [open, setOpen] = useState(false)
  return (
    <aside className="favorites-panel">
      <button className="favorites-toggle" type="button" aria-expanded={open} onClick={() => setOpen(!open)}>
        ★ Yêu thích ({items.length})
      </button>
      {open && <div className="favorites-content">
          {loading && <p className="muted">Đang tải…</p>}
          {error && <p className="favorites-error" role="alert">{error}</p>}
          <h3>Quán đã lưu</h3>
          {!loading && !items.length && <p className="muted">Bạn chưa lưu quán nào.</p>}
          {items.map((poi) => <div className="favorite-row" key={poi.id}>
            <button type="button" className="favorite-name" onClick={() => onSelect(poi)}>{poi.name}</button>
            <button type="button" aria-label={`Bỏ lưu ${poi.name}`} onClick={() => onRemove(poi)}>×</button>
          </div>)}
      </div>}
    </aside>
  )
}
