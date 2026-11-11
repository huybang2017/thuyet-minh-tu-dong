import { useEffect, useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { MapPicker } from '../components/MapPicker'
import { Field, ImageManager, Notice, Table, Tabs, useAction, useList } from '../components/Common'
import { api } from '../services/api'
import { useAuth } from '../stores/authStore'

const O = '/api/v1/owner'
const num = (v) => (v === '' ? undefined : Number(v))

/** Lane duy nhất cho owner chưa xác minh: trạng thái đơn + thông báo. */
function Pending({ onChecked }) {
  const [st, setSt] = useState(null)
  const notes = useList(`${O}/notifications`)
  const { refresh } = useAuth()
  const { msg, err, run } = useAction()
  useEffect(() => { api(`${O}/registration-status`).then(setSt).catch(() => {}) }, [])
  return (
    <main className="card">
      <h2>Trạng thái đăng ký</h2>
      {st && <p>Quán <b>{st.shop_name}</b>: <span className={`badge ${st.status === 'approved' ? 'on' : 'off'}`}>{st.status}</span>
        {st.admin_note && <> — {st.admin_note}</>}</p>}
      <button className="btn" onClick={() => run(async () => { await refresh(); onChecked?.() }, 'Đã kiểm tra lại')}>Kiểm tra lại</button>
      <Notice msg={msg} err={err} />
      <h3>Thông báo</h3>
      <Table rows={notes.items} empty="Chưa có thông báo" cols={[{ h: 'Tiêu đề', k: 'title' }, { h: 'Nội dung', k: 'body' }]} />
    </main>
  )
}

function Shops() {
  const pois = useList(`${O}/pois`)
  const subs = useList(`${O}/submissions`)
  const { msg, err, run } = useAction()
  const [edit, setEdit] = useState(null)
  const [picking, setPicking] = useState(false)
  const [ai, setAi] = useState({ usage: null, busy: false })
  const empty = { name: '', description: '', address: '', lat: '10.7608', lng: '106.7042', images: [] }
  const [f, setF] = useState(empty)
  const refreshUsage = () => api('/api/v1/ai/usage').then((u) => setAi((a) => ({ ...a, usage: u }))).catch(() => {})
  useEffect(() => { refreshUsage() }, [])
  const body = () => ({ name: f.name, description: f.description, address: f.address || '', lat: num(f.lat), lng: num(f.lng), images: f.images })
  const submit = (e) => {
    e.preventDefault()
    run(async () => {
      if (edit) await api(`${O}/pois/${edit}`, { method: 'PUT', body: { description: f.description, name: f.name, address: f.address || '', images: f.images } })
      else await api(`${O}/pois`, { method: 'POST', body: body() })
      setEdit(null); setF(empty); await subs.reload()
    }, 'Đã gửi — chờ quản trị viên duyệt mới hiển thị trên app')
  }
  const enhance = () => run(async () => {
    setAi((a) => ({ ...a, busy: true }))
    try { const r = await api('/api/v1/ai/enhance-description', { method: 'POST', body: { name: f.name, description: f.description } }); setF({ ...f, description: r.description }) }
    finally { setAi((a) => ({ ...a, busy: false })); refreshUsage() }
  }, 'AI đã viết lại mô tả — hãy kiểm tra trước khi gửi')
  return (
    <div>
      <Notice msg={msg} err={err} />
      <h3>{edit ? 'Sửa quán' : 'Gửi quán mới'}</h3>
      <form className="inline-form" onSubmit={submit}>
        <Field label="Tên quán"><input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} required /></Field>
        <Field label="Mô tả"><textarea rows={4} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} required /></Field>
        <Field label="Địa chỉ"><input value={f.address} onChange={(e) => setF({ ...f, address: e.target.value })} maxLength={200} /></Field>
        <ImageManager value={f.images} onChange={(images) => setF((cur) => ({ ...cur, images }))} />
        {!edit && <div className="row"><Field label="Lat"><input value={f.lat} onChange={(e) => setF({ ...f, lat: e.target.value })} /></Field>
          <Field label="Lng"><input value={f.lng} onChange={(e) => setF({ ...f, lng: e.target.value })} /></Field></div>}
        {!edit && <p><button type="button" className="btn ghost" onClick={() => setPicking(true)}>📍 Chọn vị trí trên bản đồ</button></p>}
        <button className="btn" type="submit">Gửi duyệt</button>{' '}
        <button type="button" className="btn ghost" disabled={ai.busy || !f.name || !f.description} onClick={enhance}>
          {ai.busy ? 'Đang xử lý…' : 'Nâng cấp mô tả bằng AI'}</button>
        {ai.usage && <span className="muted"> Lượt AI hôm nay: {ai.usage.used}/{ai.usage.limit ?? '∞'}</span>}
        {edit && <button type="button" className="btn ghost" onClick={() => { setEdit(null); setF(empty) }}>Huỷ sửa</button>}
      </form>
      <MapPicker open={picking} lat={f.lat} lng={f.lng} onClose={() => setPicking(false)}
        onSelect={(la, lo) => setF((cur) => ({ ...cur, lat: la.toFixed(6), lng: lo.toFixed(6) }))} />
      <h3>Quán của tôi</h3>
      <Table rows={pois.items} empty="Chưa có quán nào được duyệt" cols={[{ h: 'Ảnh', render: (p) => (p.images?.[0] ? <img className="mini" src={p.images[0]} alt="" /> : '—') }, { h: 'Tên', k: 'name' }, { h: 'Public', render: (p) => (p.is_active ? '✓' : '—') },
        { h: '', render: (p) => <button onClick={() => { setEdit(p.id); setF({ ...empty, name: p.name, description: p.description, address: p.address || '', images: p.images || [] }) }}>Sửa</button> }]} />
      <h3>Bài đã gửi</h3>
      <Table rows={subs.items} cols={[{ h: 'Loại', k: 'type' }, { h: 'Tên', render: (s) => s.data?.name }, { h: 'Trạng thái', k: 'status' }, { h: 'Ghi chú admin', k: 'admin_note' }]} />
    </div>
  )
}

function Notifications() {
  const { items, raw, reload } = useList(`${O}/notifications`)
  const [open, setOpen] = useState(null)
  const read = async (n) => { setOpen(n); if (!n.read) { await api(`${O}/notifications/${n.id}/read`, { method: 'POST' }); reload() } }
  return (
    <div><p className="muted">Chưa đọc: {raw?.unread ?? 0}</p>
      <Table rows={items} empty="Chưa có thông báo" cols={[{ h: '', render: (n) => (n.read ? '' : '●') },
        { h: 'Tiêu đề', render: (n) => <a href="#" onClick={(e) => { e.preventDefault(); read(n) }}>{n.title}</a> },
        { h: 'Thời gian', render: (n) => n.created_at?.slice(0, 16).replace('T', ' ') }]} />
      {open && <div className="card"><h4>{open.title}</h4><p>{open.body || '(không có ghi chú)'}</p></div>}
    </div>
  )
}

export default function OwnerPage() {
  const { user, ready, logout } = useAuth()
  const nav = useNavigate()
  const [tab, setTab] = useState('shops')
  const notes = useList(`${O}/notifications`)
  useEffect(() => { const t = setInterval(notes.reload, 30000); return () => clearInterval(t) }, [notes.reload])
  if (!ready) return <p className="muted pad">Đang tải…</p>
  if (!user) return <Navigate to="/login" replace />
  if (user.role !== 'poi_owner') return <Navigate to="/admin" replace />
  const verified = user.is_poi_owner_verified
  return (
    <div className="page">
      <header className="bar"><strong>Cổng chủ quán — {user.display_name || user.username}</strong>
        <span className="spacer" /><span title="Thông báo chưa đọc">🔔 {notes.raw?.unread ?? 0}</span>
        <Link to="/" className="lnk">Bản đồ</Link>
        <button className="btn ghost light" onClick={async () => { await logout(); nav('/login') }}>Đăng xuất</button></header>
      {!verified ? <Pending onChecked={notes.reload} /> : (<>
        <Tabs tabs={[{ id: 'shops', label: 'Quán & bài gửi' }, { id: 'notes', label: 'Thông báo' }]} current={tab} onChange={(t) => { setTab(t); notes.reload() }} />
        <main className="card">{tab === 'shops' ? <Shops /> : <Notifications />}</main></>)}
    </div>
  )
}
