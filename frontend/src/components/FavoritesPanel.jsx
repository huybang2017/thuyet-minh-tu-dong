import { useState } from 'react'
import { Link } from 'react-router-dom'

export default function FavoritesPanel({ user, items, recommendations, loading, error, onSelect, onRemove }) {
  const [open, setOpen] = useState(false)
  return (
    <aside className="favorites-panel">
      <button className="favorites-toggle" type="button" aria-expanded={open} onClick={() => setOpen(!open)}>
        ★ Yêu thích{user ? ` (${items.length})` : ''}
      </button>
      {open && <div className="favorites-content">
        {!user ? <p>Đăng nhập để lưu quán và nhận gợi ý. <Link to="/login">Đăng nhập</Link></p> : <>
          {loading && <p className="muted">Đang tải…</p>}
          {error && <p className="favorites-error" role="alert">{error}</p>}
          <h3>Quán đã lưu</h3>
          {!loading && !items.length && <p className="muted">Bạn chưa lưu quán nào.</p>}
          {items.map((poi) => <div className="favorite-row" key={poi.id}>
            <button type="button" className="favorite-name" onClick={() => onSelect(poi)}>{poi.name}</button>
            <button type="button" aria-label={`Bỏ lưu ${poi.name}`} onClick={() => onRemove(poi)}>×</button>
          </div>)}
          <h3>Gợi ý cho bạn</h3>
          {!items.length && !loading && <p className="muted">Lưu một vài quán để nhận gợi ý theo món ăn và mô tả.</p>}
          {!!items.length && !recommendations.length && !loading && <p className="muted">Chưa có gợi ý phù hợp.</p>}
          {recommendations.map((poi) => <button type="button" className="recommendation-row" key={poi.id} onClick={() => onSelect(poi)}>
            <strong>{poi.name}</strong><small>{poi.recommendation_reason}</small>
          </button>)}
        </>}
      </div>}
    </aside>
  )
}
