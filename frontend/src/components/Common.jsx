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
  const reload = useCallback(async () => {
    try { const d = await api(path); setRaw(d); setItems(d[key] || []); setError('') }
    catch (e) { setError(e.message) }
  }, [path, key])
  useEffect(() => { reload() }, [reload])
  return { items, raw, error, reload }
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
