import { create } from 'zustand'
import { A, api } from '../services/api'

export const useAuth = create((set, get) => ({
  user: null,
  permissions: [],
  ready: false,
  async init() {
    try {
      const d = await api(`${A}/auth/me`)
      set({ user: d.user, permissions: d.permissions, ready: true })
    } catch {
      set({ user: null, permissions: [], ready: true })
    }
  },
  async login(username, password) {
    const d = await api(`${A}/auth/login`, { method: 'POST', body: { username, password } })
    set({ user: d.user, permissions: d.permissions })
    return d.user
  },
  async refresh() {
    const d = await api(`${A}/auth/refresh`, { method: 'POST' })
    set({ user: d.user, permissions: d.permissions })
    return d.user
  },
  async logout() {
    await api(`${A}/auth/logout`, { method: 'POST' }).catch(() => {})
    set({ user: null, permissions: [] })
  },
  can: (p) => get().permissions.includes(p),
}))
