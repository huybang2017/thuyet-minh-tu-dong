import { create } from 'zustand'

/** Làn 2 — UI bundles. Quick-start bằng English, chuyển hẳn khi bundle đích ready. */
const BUILTIN = { 'app.title': 'Auto Narration Tour', loading: 'Loading...' }

export const useUi = create((set, get) => ({
  locale: 'en',
  strings: BUILTIN,
  status: 'ready',
  t: (k) => get().strings[k] ?? BUILTIN[k] ?? k,
  async load(locale) {
    set({ locale })
    const fetchOnce = async () => {
      try {
        const res = await fetch(`/api/v1/ui-bundles/${locale}`)
        if (!res.ok) return
        const b = await res.json()
        if (get().locale !== locale) return
        set({ strings: b.strings, status: b.status })
        if (b.status !== 'ready') setTimeout(fetchOnce, 4000) // long-tail: server đang dịch nền
      } catch { /* giữ bản hiện có */ }
    }
    await fetchOnce()
  },
}))
