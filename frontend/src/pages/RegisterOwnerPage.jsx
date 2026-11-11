import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Field, Notice, useAction } from '../components/Common'
import { A, api } from '../services/api'

const EMPTY = { username: '', email: '', password: '', display_name: '', shop_name: '', phone: '' }

export default function RegisterOwnerPage() {
  const [f, setF] = useState(EMPTY)
  const [done, setDone] = useState(false)
  const { err, run } = useAction()
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const submit = async (e) => {
    e.preventDefault()
    if (await run(() => api(`${A}/auth/register-owner`, { method: 'POST', body: f }))) setDone(true)
  }
  if (done) return (
    <div className="card narrow"><h2>Đã gửi đăng ký</h2>
      <p>Đơn của bạn đang chờ quản trị viên duyệt. Sau khi duyệt, hãy <Link to="/login">đăng nhập</Link> để vào cổng chủ quán.</p></div>
  )
  return (
    <div className="card narrow">
      <h2>Đăng ký chủ quán</h2>
      <form onSubmit={submit}>
        <Field label="Tên đăng nhập"><input value={f.username} onChange={set('username')} required minLength={3} /></Field>
        <Field label="Email"><input type="email" value={f.email} onChange={set('email')} required /></Field>
        <Field label="Mật khẩu (≥ 8 ký tự)"><input type="password" value={f.password} onChange={set('password')} required minLength={8} /></Field>
        <Field label="Họ tên"><input value={f.display_name} onChange={set('display_name')} required /></Field>
        <Field label="Tên quán"><input value={f.shop_name} onChange={set('shop_name')} required /></Field>
        <Field label="Số điện thoại"><input value={f.phone} onChange={set('phone')} required /></Field>
        <Notice err={err} />
        <button className="btn" type="submit">Gửi đăng ký</button>
      </form>
      <p className="muted"><Link to="/login">Đã có tài khoản?</Link></p>
    </div>
  )
}
