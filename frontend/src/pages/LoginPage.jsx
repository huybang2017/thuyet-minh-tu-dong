import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Field, Notice, useAction } from '../components/Common'
import { useAuth } from '../stores/authStore'

export default function LoginPage() {
  const [u, setU] = useState('')
  const [p, setP] = useState('')
  const { login } = useAuth()
  const nav = useNavigate()
  const { err, run } = useAction()
  const submit = async (e) => {
    e.preventDefault()
    const user = await run(() => login(u, p))
    if (user) nav(user.role === 'poi_owner' ? '/owner' : user.role === 'user' ? '/' : '/admin')
  }
  return (
    <div className="card narrow">
      <h2>Đăng nhập</h2>
      <form onSubmit={submit}>
        <Field label="Tên đăng nhập"><input value={u} onChange={(e) => setU(e.target.value)} autoComplete="username" required /></Field>
        <Field label="Mật khẩu"><input type="password" value={p} onChange={(e) => setP(e.target.value)} autoComplete="current-password" required /></Field>
        <Notice err={err} />
        <button className="btn" type="submit">Đăng nhập</button>
      </form>
      <p className="muted">Là chủ quán? <Link to="/register-owner">Đăng ký tại đây</Link> · <Link to="/">Về bản đồ</Link></p>
    </div>
  )
}
