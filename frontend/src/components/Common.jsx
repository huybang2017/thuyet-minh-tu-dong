import { useCallback, useEffect, useState } from 'react'
import { api } from '../services/api'

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
