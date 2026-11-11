import { useCallback, useEffect, useState } from 'react'
import { api, IMAGE_TYPES, uploadImage } from '../services/api'

export const MAX_POI_IMAGES = 8

/** Quản lý ảnh quán: tải lên (JPEG/PNG/WebP ≤ 2 MB), xoá, đưa ảnh lên làm ảnh đại diện. */
export function ImageManager({ value = [], onChange }) {
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const add = async (e) => {
    const files = [...e.target.files].slice(0, MAX_POI_IMAGES - value.length)
    e.target.value = ''
    if (!files.length) return
    setBusy(true); setErr('')
    const next = [...value]
    try {
      for (const f of files) { const url = await uploadImage(f); if (!next.includes(url)) next.push(url) }
    } catch (ex) { setErr(ex.message) } finally { setBusy(false); onChange(next) }
  }
  const remove = (u) => onChange(value.filter((x) => x !== u))
  const first = (u) => onChange([u, ...value.filter((x) => x !== u)])
  return (
    <div className="field">
      <span>Ảnh quán ({value.length}/{MAX_POI_IMAGES}) — ảnh đầu tiên là ảnh đại diện</span>
      <div className="thumbs">
        {value.map((u, i) => (
          <figure key={u} className="thumb">
            <img src={u} alt={`Ảnh ${i + 1}`} loading="lazy" />
            <figcaption className="actions">
              {i > 0 && <button type="button" onClick={() => first(u)} title="Đặt làm ảnh đại diện">★</button>}
              <button type="button" className="danger" onClick={() => remove(u)} title="Xoá ảnh">✕</button>
            </figcaption>
          </figure>))}
        {value.length < MAX_POI_IMAGES && (
          <label className="thumb add" aria-busy={busy}>
            {busy ? 'Đang tải…' : '+ Thêm ảnh'}
            <input type="file" accept={IMAGE_TYPES.join(',')} multiple onChange={add} disabled={busy} hidden />
          </label>)}
      </div>
      {err && <div className="notice err">{err}</div>}
    </div>
  )
}

export function useList(path, key = 'items') {
  const [items, setItems] = useState([])
  const [error, setError] = useState('')
  const [raw, setRaw] = useState(null)
  const [loading, setLoading] = useState(false)
  const reload = useCallback(async () => {
    try {
      setLoading(true); setError('')
      const d = await api(path); setRaw(d); setItems(d[key] || [])
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }, [path, key])
  useEffect(() => { reload() }, [reload])
  return { items, raw, error, reload, loading }
}

export function useAction() {
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')
  const run = async (fn, ok = 'Thành công') => {
    setErr(''); setMsg('')
    try { const r = await fn(); setMsg(ok); return r } catch (e) { setErr(e.message); return null }
  }
  return { msg, err, run, clear: () => { setMsg(''); setErr('') } }
}

export function Notice({ msg, err }) {
  if (!msg && !err) return null
  return <div className={err ? 'notice err' : 'notice ok'} role="status">{err || msg}</div>
}

export function Table({ cols, rows, empty = 'Chưa có dữ liệu' }) {
  if (!rows.length) return <p className="muted">{empty}</p>
  return (
    <div className="tablewrap"><table>
      <thead><tr>{cols.map((c) => <th key={c.h}>{c.h}</th>)}</tr></thead>
      <tbody>{rows.map((r, i) => <tr key={r.id ?? i}>{cols.map((c) => <td key={c.h}>{c.render ? c.render(r) : String(r[c.k] ?? '')}</td>)}</tr>)}</tbody>
    </table></div>
  )
}

export function SkeletonTable({ count = 5 }) {
  return (
    <div className="tablewrap"><table>
      <thead><tr>{['Tên','Khu vực','Trạng thái','Audio','Thao tác'].map((h) => <th key={h}>{h}</th>)}</tr></thead>
      <tbody>{[...Array(count)].map((_, i) => (
        <tr key={i}><td><span className="skeleton w" /></td><td><span className="skeleton" /></td><td><span className="skeleton" /></td><td><span className="skeleton" /></td><td><span className="skeleton" /></td></tr>
      ))}</tbody>
    </table></div>
  )
}

export function Field({ label, children }) {
  return <label className="field"><span>{label}</span>{children}</label>
}

export function Tabs({ tabs, current, onChange }) {
  return (
    <div className="tabs" role="tablist">
      {tabs.map((t) => (
        <button key={t.id} role="tab" aria-selected={current === t.id} className={current === t.id ? 'tab on' : 'tab'}
          onClick={() => onChange(t.id)}>{t.label}</button>
      ))}
    </div>
  )
}

export function Modal({ open, title, onClose, children }) {
  if (!open) return null
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label={title}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <header>
          <h2>{title}</h2>
          <button className="close" onClick={onClose} aria-label="Đóng">×</button>
        </header>
        <div className="body">{children}</div>
      </div>
    </div>
  )
}

export function ConfirmModal({ open, title, content, onConfirm, onCancel, confirmLabel = 'Xác nhận', cancelLabel = 'Huỷ' }) {
  if (!open) return null
  return (
    <Modal open={open} title={title} onClose={onCancel}>
      <div className="body">{content}</div>
      <div className="footer">
        <button className="btn ghost" onClick={onCancel}>{cancelLabel}</button>
        <button className="btn danger" onClick={onConfirm}>{confirmLabel}</button>
      </div>
    </Modal>
  )
}

export function Toast({ open, msg, err, onClose }) {
  if (!open && !msg && !err) return null
  return (
    <div className="toast-overlay">
      <div className={err ? 'toast-item err' : 'toast-item'} role="status" onClick={onClose}>
        {err || msg}
      </div>
    </div>
  )
}
