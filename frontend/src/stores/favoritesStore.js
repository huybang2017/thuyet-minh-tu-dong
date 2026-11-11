import { create } from 'zustand'
const STORAGE_KEY = 'food-tour-favorites'

function readFavorites() {
  try {
    const value = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
    return Array.isArray(value) ? value : []
  } catch {
    return []
  }
}

function saveFavorites(items) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(items))
}

export const useFavorites = create((set, get) => ({
  items: [],
  recommendations: [],
  loading: false,
  error: '',
  load: () => {
    set({ items: readFavorites(), recommendations: [], loading: false, error: '' })
  },
  toggle: (poi) => {
    const items = get().items
    const next = items.some((item) => item.id === poi.id)
      ? items.filter((item) => item.id !== poi.id)
      : [{ ...poi, favorite_at: new Date().toISOString() }, ...items]
    saveFavorites(next)
    set({ items: next, error: '' })
  },
  clear: () => set({ items: readFavorites(), recommendations: [], error: '', loading: false }),
}))
