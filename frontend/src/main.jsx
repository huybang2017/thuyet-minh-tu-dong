import { StrictMode, useEffect } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import MapApp from './pages/MapApp.jsx'
import LoginPage from './pages/LoginPage.jsx'
import RegisterOwnerPage from './pages/RegisterOwnerPage.jsx'
import AdminPage from './pages/AdminPage.jsx'
import OwnerPage from './pages/OwnerPage.jsx'
import { ForgotPasswordPage, ResetPasswordPage } from './pages/PasswordResetPages.jsx'
import { useAuth } from './stores/authStore'
import './styles.css'

function Root() {
  const init = useAuth((s) => s.init)
  useEffect(() => { init() }, [init])
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register-owner" element={<RegisterOwnerPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route path="/admin/*" element={<AdminPage />} />
      <Route path="/owner/*" element={<OwnerPage />} />
      <Route path="*" element={<MapApp />} />
    </Routes>
  )
}

// Bản cũ từng đăng ký service worker/IndexedDB (offline đã bỏ): để trình duyệt tải public/sw.js
// (kill-switch) tự gỡ worker + cache cũ, và xoá database còn sót.
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.getRegistrations()
    .then((rs) => rs.forEach((r) => r.update().catch(() => {})))
    .catch(() => {})
}
try { ['workbox-expiration'].forEach((n) => indexedDB.deleteDatabase(n)) } catch { /* ignore */ }

createRoot(document.getElementById('root')).render(<StrictMode><BrowserRouter><Root /></BrowserRouter></StrictMode>)
