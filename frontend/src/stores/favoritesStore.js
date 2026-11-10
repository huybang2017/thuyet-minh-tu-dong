import { create } from 'zustand'
import { api } from '../services/api'

const BASE = '/api/v1/favorites'

export const useFavorites = create((set, get) => ({
  items: [],
  recommendations: [],
  loading: false,
  error: '',
  load: async () => {
    set({ loading: true, error: '' })
    try {
      const [favorites, recommendations] = await Promise.all([
        api(BASE), api(`${BASE}/recommendations`),
      ])
      set({ items: favorites.items, recommendations: recommendations.items, loading: false })
    } catch (error) {
      set({ loading: false, error: error.message || 'Không tải được danh sách yêu thích.' })
    }
  },
  toggle: async (poi) => {
    const saved = get().items.some((item) => item.id === poi.id)
    set({ error: '' })
    try {
      await api(`${BASE}/${encodeURIComponent(poi.id)}`, { method: saved ? 'DELETE' : 'POST' })
      await get().load()
    } catch (error) {
      set({ error: error.message || 'Không cập nhật được quán yêu thích.' })
    }
  },
  clear: () => set({ items: [], recommendations: [], error: '', loading: false }),
}))
