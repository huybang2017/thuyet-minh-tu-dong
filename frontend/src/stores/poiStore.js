import { create } from 'zustand'
import { mergeDelta } from '../services/syncUtils'
import { useUi } from './uiStore'

export const LANGS = { vi: 'Tiếng Việt', en: 'English', zh: '中文', ja: '日本語', ko: '한국어' }
const stored = () => { try { return localStorage.getItem('lang') } catch { return null } }

export const usePoiStore = create((set, get) => ({
  pois: [],
  lang: stored() || 'vi',
  hasChosenLang: !!stored(),
  etag: null,
  cursor: null,
  unreachable: false, // true khi không gọi được máy chủ (giữ danh sách đang có)
  loading: false,

  /** Full sync lần đầu/đổi ngôn ngữ; delta sync (ETag + updated_after) khi làm mới. */
  async load({ forceFull = false } = {}) {
    const { lang, etag, cursor, pois } = get()
    const delta = !forceFull && cursor && pois.length > 0
    const headers = etag && !forceFull ? { 'If-None-Match': etag } : {}
    const url = `/api/v1/poi/load-all?lang=${lang}` + (delta ? `&updated_after=${encodeURIComponent(cursor)}` : '')
    set({ loading: true })
    try {
      const res = await fetch(url, { headers })
      if (get().lang !== lang) return
      if (res.status === 304) { set({ unreachable: false, loading: false }); return }
      if (!res.ok) throw new Error(`load-all ${res.status}`)
      const data = await res.json()
      const next = data.sync_mode === 'delta' ? mergeDelta(pois, data) : data.pois
      set({ pois: next, etag: res.headers.get('ETag'), cursor: data.sync_cursor, unreachable: false, loading: false })
    } catch {
      if (get().lang === lang) set({ unreachable: true, loading: false })
    }
  },

  async setLang(lang) {
    try { localStorage.setItem('lang', lang) } catch { /* ignore */ }
    set({ lang, hasChosenLang: true, etag: null, cursor: null })
    useUi.getState().load(lang)
    await get().load({ forceFull: true })
    if (lang !== 'vi' && !get().unreachable) {
      // warmup full-corpus dưới nền, rồi đồng bộ lại khi có bản dịch mới
      fetch(`/api/v1/localizations/warmup?lang=${lang}`, { method: 'POST' }).catch(() => {})
      const poll = async (n) => {
        if (get().lang !== lang || n > 8) return
        await get().load({ forceFull: true })
        if (get().pois.some((p) => p.is_fallback)) setTimeout(() => poll(n + 1), 15000)
      }
      setTimeout(() => poll(0), 12000)
    }
  },
}))
