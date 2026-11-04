import { useEffect, useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { Field, Notice, Table, Tabs, useAction, useList } from '../components/Common'
import { A, api } from '../services/api'
import { useAuth } from '../stores/authStore'

const POI_EMPTY = { name: '', description: '', lat: '10.7608', lng: '106.7042', trigger_radius: '30', audio_priority: '3' }
const num = (v) => (v === '' || v == null ? undefined : Number(v))

function PoiForm({ initial, onSubmit, onCancel }) {
  const [f, setF] = useState(initial)
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  return (
    <form className="inline-form" onSubmit={(e) => { e.preventDefault(); onSubmit({
      name: f.name, description: f.description, lat: num(f.lat), lng: num(f.lng),
      trigger_radius: num(f.trigger_radius), audio_priority: num(f.audio_priority) }) }}>
      <Field label="Tên"><input value={f.name} onChange={set('name')} required /></Field>
      <Field label="Mô tả (tiếng Việt)"><textarea value={f.description} onChange={set('description')} required rows={3} /></Field>
      <div className="row">
        <Field label="Lat"><input value={f.lat} onChange={set('lat')} required /></Field>
        <Field label="Lng"><input value={f.lng} onChange={set('lng')} required /></Field>
        <Field label="Bán kính (m)"><input value={f.trigger_radius} onChange={set('trigger_radius')} /></Field>
        <Field label="Ưu tiên audio (1=cao)"><input value={f.audio_priority} onChange={set('audio_priority')} /></Field>
      </div>
      <button className="btn" type="submit">Lưu</button> {onCancel && <button type="button" className="btn ghost" onClick={onCancel}>Huỷ</button>}
    </form>
  )
}

function PoiTab() {
  const { items, error, reload } = useList(`${A}/pois`)
  const { can } = useAuth()
  const { msg, err, run } = useAction()
  const [editing, setEditing] = useState(null)
  const [formKey, setFormKey] = useState(0)
  const act = (fn, ok) => run(async () => { await fn(); await reload() }, ok)
  return (
    <div>
      <Notice msg={msg} err={err || error} />
      {can('poi:create') && <details key={formKey}><summary>+ Thêm POI</summary>
        <PoiForm initial={POI_EMPTY} onSubmit={(b) => act(async () => { await api(`${A}/pois`, { method: 'POST', body: b }); setFormKey((k) => k + 1) }, 'Đã tạo — audio đang được sinh, POI sẽ tự bật khi sẵn sàng')} /></details>}
      {editing && <PoiForm initial={{ ...POI_EMPTY, ...editing, lat: String(editing.lat), lng: String(editing.lng), trigger_radius: String(editing.trigger_radius ?? ''), audio_priority: String(editing.audio_priority ?? '') }}
        onCancel={() => setEditing(null)}
        onSubmit={(b) => act(async () => { await api(`${A}/pois/${editing.id}`, { method: 'PUT', body: b }); setEditing(null) }, 'Đã cập nhật')} />}
      <Table rows={items} cols={[
        { h: 'Tên', k: 'name' },
        { h: 'Trạng thái', render: (p) => <span className={p.is_active ? 'badge on' : 'badge off'}>{p.is_active ? 'Public' : p.activation_requested ? 'Chờ audio' : 'Ẩn'}</span> },
        { h: 'Audio', k: 'audio_status' },
        { h: 'Thao tác', render: (p) => (
          <span className="actions">
            {can('poi:update') && <button onClick={() => setEditing(p)}>Sửa</button>}
            {can('poi:toggle') && <button onClick={() => act(() => api(`${A}/pois/${p.id}/toggle`, { method: 'POST', body: { active: !p.is_active } }))}>{p.is_active ? 'Tắt' : 'Bật'}</button>}
            {can('poi:update') && <button onClick={() => act(() => api(`${A}/pois/${p.id}/regenerate-audio`, { method: 'POST' }), 'Đã xếp hàng sinh lại audio')}>Sinh lại audio</button>}
            {can('poi:delete') && <button className="danger" onClick={() => window.confirm(`Xoá "${p.name}"?`) && act(() => api(`${A}/pois/${p.id}`, { method: 'DELETE' }), 'Đã xoá')}>Xoá</button>}
          </span>) },
      ]} />
    </div>
  )
}

function AudioTab() {
  const [tasks, setTasks] = useState([])
  const { msg, err, run } = useAction()
  useEffect(() => {
    const es = new EventSource(`${A}/audio-tasks-stream`, { withCredentials: true })
    es.onmessage = (e) => setTasks(JSON.parse(e.data))
    es.onerror = () => { es.close(); api(`${A}/audio-tasks`).then((d) => setTasks(d.items)).catch(() => {}) }
    return () => es.close()
  }, [])
  const ctl = (id, a) => run(() => api(`${A}/audio-tasks/${id}/${a}`, { method: 'POST' }), `Đã ${a}`)
  return (
    <div><Notice msg={msg} err={err} />
      <p className="muted">Tiến độ cập nhật real-time qua SSE.</p>
      <Table rows={tasks} cols={[
        { h: 'POI', k: 'poi_id' }, { h: 'Trạng thái', k: 'status' },
        { h: 'Tiến độ', render: (t) => <span><progress max={t.total} value={t.done} /> {t.done}/{t.total}</span> },
        { h: 'Lỗi', render: (t) => t.error || '' },
        { h: '', render: (t) => ['running', 'paused', 'queued'].includes(t.status) && (
          <span className="actions">
            {t.status === 'running' && <button onClick={() => ctl(t.id, 'pause')}>Tạm dừng</button>}
            {t.status === 'paused' && <button onClick={() => ctl(t.id, 'resume')}>Tiếp tục</button>}
            <button className="danger" onClick={() => ctl(t.id, 'cancel')}>Huỷ</button></span>) },
      ]} />
    </div>
  )
}

function MenuTab() {
  const { items, error, reload } = useList(`${A}/menus`)
  const pois = useList(`${A}/pois`)
  const { can } = useAuth()
  const { msg, err, run } = useAction()
  const [f, setF] = useState({ poi_id: '', name: '', price: '' })
  const act = (fn, ok) => run(async () => { await fn(); await reload() }, ok)
  return (
    <div><Notice msg={msg} err={err || error} />
      {can('menu:create') && <form className="inline-form row" onSubmit={(e) => { e.preventDefault(); act(() => api(`${A}/menus`, { method: 'POST', body: { ...f, price: Number(f.price) } }), 'Đã thêm món') }}>
        <Field label="Quán"><select value={f.poi_id} onChange={(e) => setF({ ...f, poi_id: e.target.value })} required>
          <option value="">— chọn —</option>{pois.items.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></Field>
        <Field label="Tên món"><input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} required /></Field>
        <Field label="Giá (đ)"><input value={f.price} onChange={(e) => setF({ ...f, price: e.target.value })} required inputMode="numeric" /></Field>
        <button className="btn" type="submit">Thêm</button></form>}
      <Table rows={items} cols={[{ h: 'Quán', k: 'poi_id' }, { h: 'Món', k: 'name' }, { h: 'Giá', k: 'price' },
        { h: '', render: (m) => can('menu:delete') && <button className="danger" onClick={() => act(() => api(`${A}/menus/${m.id}`, { method: 'DELETE' }), 'Đã xoá')}>Xoá</button> }]} />
    </div>
  )
}

function UserTab() {
  const { items, error, reload } = useList(`${A}/users`)
  const roles = useList(`${A}/roles`)
  const { can } = useAuth()
  const { msg, err, run } = useAction()
  const [f, setF] = useState({ username: '', password: '', role: 'user' })
  const act = (fn, ok) => run(async () => { await fn(); await reload() }, ok)
  const roleNames = roles.items.length ? roles.items.map((r) => r.name) : ['user', 'poi_owner', 'admin']
  return (
    <div><Notice msg={msg} err={err || error} />
      {can('user:create') && <form className="inline-form row" onSubmit={(e) => { e.preventDefault(); act(() => api(`${A}/users`, { method: 'POST', body: f }), 'Đã tạo user') }}>
        <Field label="Username"><input value={f.username} onChange={(e) => setF({ ...f, username: e.target.value })} required minLength={3} /></Field>
        <Field label="Mật khẩu"><input type="password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} required minLength={8} /></Field>
        <Field label="Role"><select value={f.role} onChange={(e) => setF({ ...f, role: e.target.value })}>{roleNames.map((r) => <option key={r}>{r}</option>)}</select></Field>
        <button className="btn" type="submit">Tạo</button></form>}
      <Table rows={items} cols={[{ h: 'Username', k: 'username' }, { h: 'Role', k: 'role' },
        { h: 'Owner verified', render: (u) => (u.is_poi_owner_verified ? '✓' : '—') },
        { h: 'Hoạt động', render: (u) => (u.is_active ? '✓' : 'Đã khoá') },
        { h: '', render: (u) => (
          <span className="actions">
            {can('user:update') && <button onClick={() => act(() => api(`${A}/users/${u.id}`, { method: 'PUT', body: { is_active: !u.is_active } }))}>{u.is_active ? 'Khoá' : 'Mở khoá'}</button>}
            {can('user:delete') && <button className="danger" onClick={() => window.confirm(`Xoá ${u.username}?`) && act(() => api(`${A}/users/${u.id}`, { method: 'DELETE' }), 'Đã xoá')}>Xoá</button>}
          </span>) }]} />
    </div>
  )
}

function RoleTab() {
  const { items, error, reload } = useList(`${A}/roles`)
  const perms = useList(`${A}/permissions`, 'all')
  const { msg, err, run } = useAction()
  const [f, setF] = useState({ name: '', permissions: [] })
  const act = (fn, ok) => run(async () => { await fn(); await reload() }, ok)
  const all = perms.raw?.domains || {}
  const toggle = (p) => setF({ ...f, permissions: f.permissions.includes(p) ? f.permissions.filter((x) => x !== p) : [...f.permissions, p] })
  return (
    <div><Notice msg={msg} err={err || error} />
      <details><summary>+ Tạo role mới</summary>
        <form className="inline-form" onSubmit={(e) => { e.preventDefault(); act(() => api(`${A}/roles`, { method: 'POST', body: f }), 'Đã tạo role') }}>
          <Field label="Tên role (a-z, 0-9, _)"><input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} required pattern="[a-z0-9_]+" /></Field>
          {Object.entries(all).map(([d, acts]) => <fieldset key={d}><legend>{d}</legend>
            {acts.map((a) => <label key={a} className="chk"><input type="checkbox" checked={f.permissions.includes(`${d}:${a}`)} onChange={() => toggle(`${d}:${a}`)} />{a}</label>)}</fieldset>)}
          <button className="btn" type="submit">Tạo</button></form></details>
      <Table rows={items} cols={[{ h: 'Role', k: 'name' }, { h: 'Priority', k: 'priority' },
        { h: 'Số quyền', render: (r) => r.permissions.length },
        { h: '', render: (r) => !r.is_default && <button className="danger" onClick={() => act(() => api(`${A}/roles/${r.name}`, { method: 'DELETE' }), 'Đã xoá')}>Xoá</button> }]} />
    </div>
  )
}

function ReviewTab() {
  const regs = useList(`${A}/registrations?status=pending`)
  const subs = useList(`${A}/submissions?status=pending`)
  const { msg, err, run } = useAction()
  const [note, setNote] = useState('')
  const review = (kind, id, verb) => run(async () => {
    await api(`${A}/${kind}/${id}/${verb}`, { method: 'POST', body: { admin_note: note || null } })
    await Promise.all([regs.reload(), subs.reload()])
  }, verb === 'approve' ? 'Đã duyệt' : 'Đã từ chối')
  const btns = (kind) => (r) => (
    <span className="actions"><button onClick={() => review(kind, r.id, 'approve')}>Duyệt</button>
      <button className="danger" onClick={() => review(kind, r.id, 'reject')}>Từ chối</button></span>)
  return (
    <div><Notice msg={msg} err={err || regs.error} />
      <Field label="Ghi chú gửi tới chủ quán (admin_note)"><input value={note} onChange={(e) => setNote(e.target.value)} /></Field>
      <h3>Đơn đăng ký chủ quán</h3>
      <Table rows={regs.items} empty="Không có đơn chờ" cols={[{ h: 'User', k: 'username' }, { h: 'Quán', k: 'shop_name' }, { h: 'SĐT', k: 'phone' },
        { h: 'CCCD', render: (r) => (r.has_cccd ? 'đã mã hoá' : 'đã xoá') }, { h: '', render: btns('registrations') }]} />
      <h3>Bài gửi POI từ chủ quán</h3>
      <Table rows={subs.items} empty="Không có bài chờ duyệt" cols={[{ h: 'Loại', k: 'type' }, { h: 'Tên', render: (s) => s.data?.name },
        { h: 'Nội dung', render: (s) => (s.data?.description || '').slice(0, 80) }, { h: '', render: btns('submissions') }]} />
    </div>
  )
}

function AuditTab() {
  const { items, error } = useList(`${A}/audit-logs?limit=100`)
  return <div><Notice err={error} /><Table rows={items} cols={[{ h: 'Thời gian', render: (r) => r.timestamp?.slice(0, 19).replace('T', ' ') },
    { h: 'User', k: 'username' }, { h: 'Hành động', k: 'action' }, { h: 'Đối tượng', k: 'resource' }, { h: 'Chi tiết', k: 'detail' }]} /></div>
}

function AnalyticsTab() {
  const s = useList('/api/v1/analytics/summary', 'x')
  const o = useList(`${A}/observability`, 'cells')
  const d = s.raw
  return (
    <div><Notice err={s.error} />
      {d && <div className="stats">
        <div><b>{d.tracked_online_users}</b><span>Thiết bị đã consent đang online</span></div>
        <div><b>{d.devices}</b><span>Thiết bị trong {d.window_days} ngày</span></div>
        <div><b>{d.events?.narration_played || 0}</b><span>Lượt nghe thuyết minh</span></div>
        <div><b>{o.raw?.total ?? 0}</b><span>Điểm vị trí runtime (24h)</span></div>
      </div>}
      <p className="muted">"Online" = số anonymous device đã consent còn trong cửa sổ trượt hiện tại, không phải tổng traffic.</p>
      <h3>Top POI nghe nhiều</h3><Table rows={(d?.top_pois || []).map((x) => ({ ...x, id: x.poi_id }))} cols={[{ h: 'POI', k: 'poi_id' }, { h: 'Lượt nghe', k: 'plays' }]} />
      <h3>Vùng hoạt động (ô lưới ~110 m)</h3><Table rows={o.items.map((c, i) => ({ ...c, id: i }))} cols={[{ h: 'Lat', k: 'lat' }, { h: 'Lng', k: 'lng' }, { h: 'Số lần', k: 'count' }]} />
    </div>
  )
}

function PasswordTab() {
  const [f, setF] = useState({ old_password: '', new_password: '' })
  const { msg, err, run } = useAction()
  return (
    <form className="inline-form" onSubmit={(e) => { e.preventDefault(); run(() => api(`${A}/auth/change-password`, { method: 'POST', body: f }), 'Đã đổi mật khẩu') }}>
      <Field label="Mật khẩu cũ"><input type="password" value={f.old_password} onChange={(e) => setF({ ...f, old_password: e.target.value })} required /></Field>
      <Field label="Mật khẩu mới (≥ 8)"><input type="password" value={f.new_password} onChange={(e) => setF({ ...f, new_password: e.target.value })} required minLength={8} /></Field>
      <Notice msg={msg} err={err} /><button className="btn" type="submit">Đổi mật khẩu</button></form>
  )
}

const ALL_TABS = [
  { id: 'poi', label: 'POI', perm: 'poi:read', C: PoiTab },
  { id: 'audio', label: 'Audio tasks', perm: 'poi:read', C: AudioTab },
  { id: 'menu', label: 'Thực đơn', perm: 'menu:read', C: MenuTab },
  { id: 'review', label: 'Kiểm duyệt', perm: 'poi:approve', C: ReviewTab },
  { id: 'user', label: 'Người dùng', perm: 'user:read', C: UserTab },
  { id: 'role', label: 'Vai trò', perm: 'role:read', C: RoleTab },
  { id: 'audit', label: 'Audit log', perm: 'audit:read', C: AuditTab },
  { id: 'analytics', label: 'Thống kê', perm: 'analytics:view', C: AnalyticsTab },
  { id: 'pw', label: 'Mật khẩu', perm: null, C: PasswordTab },
]

export default function AdminPage() {
  const { user, ready, can, logout } = useAuth()
  const nav = useNavigate()
  const tabs = ALL_TABS.filter((t) => !t.perm || can(t.perm))
  const [cur, setCur] = useState(tabs[0]?.id || 'pw')
  if (!ready) return <p className="muted pad">Đang tải…</p>
  if (!user) return <Navigate to="/login" replace />
  if (user.role === 'poi_owner') return <Navigate to="/owner" replace />
  const T = (tabs.find((t) => t.id === cur) || tabs[0]).C
  return (
    <div className="page">
      <header className="bar"><strong>Quản trị — {user.username} ({user.role})</strong>
        <span className="spacer" /><Link to="/" className="lnk">Bản đồ</Link>
        <button className="btn ghost light" onClick={async () => { await logout(); nav('/login') }}>Đăng xuất</button></header>
      <Tabs tabs={tabs} current={cur} onChange={setCur} />
      <main className="card"><T /></main>
    </div>
  )
}
