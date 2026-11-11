import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Field, Notice, useAction } from '../components/Common'
import { A, api } from '../services/api'

export function ForgotPasswordPage() {
  const [id, setId] = useState('')
  const [res, setRes] = useState(null)
  const { err, run } = useAction()
  const submit = async (e) => {
    e.preventDefault()
    const r = await run(() => api(`${A}/auth/forgot-password`, { method: 'POST', body: { identifier: id.trim() } }))
    if (r) setRes(r)
  }
  return (
    <div className="card narrow">
      <h2>Quên mật khẩu</h2>
      {res ? (<>
        <Notice msg={res.message} />
        {res.dev_reset_url && (
          <p className="muted">Môi trường dev chưa cấu hình SMTP — liên kết đặt lại:{' '}
            <a href={res.dev_reset_url.replace(/^https?:\/\/[^/]+/, '')}>mở trang đặt lại mật khẩu</a></p>)}
      </>) : (
        <form onSubmit={submit}>
          <p className="muted">Nhập tên đăng nhập hoặc email. Nếu tài khoản có email, bạn sẽ nhận liên kết đặt lại (hết hạn sau 30 phút).</p>
          <Field label="Tên đăng nhập hoặc email"><input value={id} onChange={(e) => setId(e.target.value)} required minLength={3} autoComplete="username" /></Field>
          <Notice err={err} />
          <button className="btn" type="submit">Gửi liên kết</button>
        </form>)}
      <p className="muted"><Link to="/login">Quay lại đăng nhập</Link></p>
    </div>
  )
}

export function ResetPasswordPage() {
  const [params] = useSearchParams()
  const token = params.get('token') || ''
  const [pw, setPw] = useState('')
  const [pw2, setPw2] = useState('')
  const [done, setDone] = useState(false)
  const { err, run } = useAction()
  const nav = useNavigate()
  const submit = async (e) => {
    e.preventDefault()
    const r = await run(async () => {
      if (pw !== pw2) throw new Error('Hai mật khẩu không khớp')
      return api(`${A}/auth/reset-password`, { method: 'POST', body: { token, new_password: pw } })
    })
    if (r) { setDone(true); setTimeout(() => nav('/login'), 2500) }
  }
  if (!token) return (
    <div className="card narrow"><h2>Liên kết không hợp lệ</h2>
      <p><Link to="/forgot-password">Yêu cầu liên kết mới</Link></p></div>)
  return (
    <div className="card narrow">
      <h2>Đặt mật khẩu mới</h2>
      {done ? <Notice msg="Đã đặt lại mật khẩu. Đang chuyển tới trang đăng nhập…" /> : (
        <form onSubmit={submit}>
          <Field label="Mật khẩu mới (≥ 8 ký tự)"><input type="password" value={pw} onChange={(e) => setPw(e.target.value)} required minLength={8} maxLength={72} autoComplete="new-password" /></Field>
          <Field label="Nhập lại mật khẩu mới"><input type="password" value={pw2} onChange={(e) => setPw2(e.target.value)} required minLength={8} maxLength={72} autoComplete="new-password" /></Field>
          <Notice err={err} />
          <button className="btn" type="submit">Đặt lại mật khẩu</button>
        </form>)}
      <p className="muted"><Link to="/login">Quay lại đăng nhập</Link></p>
    </div>
  )
}
