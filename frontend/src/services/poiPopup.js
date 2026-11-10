import { formatPrice, menuItemLabel } from './format'

/** Tạo phần tử DOM; chữ luôn gán qua textContent nên nội dung do người dùng nhập không thể chèn HTML. */
function el(tag, cls, text) {
  const n = document.createElement(tag)
  if (cls) n.className = cls
  if (text != null) n.textContent = text
  return n
}

/**
 * Nội dung popup một quán: ảnh, mô tả, nút Nghe, thực đơn (tải khi mở popup lần đầu).
 * Trả { root, onOpen } — gọi onOpen khi popup mở.
 */
export function buildPoiPopup(poi, { t, lang, onListen, isFavorite = false, onFavorite }) {
  const root = el('div', 'poi-pop')
  if (poi.images?.length) {
    const gal = el('div', 'poi-gallery')
    poi.images.slice(0, 8).forEach((src, i) => {
      const img = el('img')
      img.src = src
      img.alt = `${poi.name} ${i + 1}`
      img.loading = 'lazy'
      gal.appendChild(img)
    })
    root.appendChild(gal)
  }
  root.appendChild(el('h3', null, poi.name))
  if (poi.is_fallback) root.appendChild(el('p', 'poi-note', t('poi.fallback')))
  root.appendChild(el('p', 'poi-desc', poi.description))
  if (onFavorite) {
    const favorite = el('button', 'btn ghost poi-favorite', `${isFavorite ? '★ Đã lưu' : '☆ Lưu yêu thích'}`)
    favorite.type = 'button'
    favorite.setAttribute('aria-pressed', String(isFavorite))
    favorite.onclick = () => onFavorite(poi)
    root.appendChild(favorite)
  }
  const listen = el('button', 'btn', `🎧 ${t('poi.listen')}`)
  listen.type = 'button'
  listen.onclick = () => onListen(poi)
  root.appendChild(listen)

  const menuBox = el('div', 'poi-menu')
  menuBox.appendChild(el('h4', null, t('poi.menu')))
  const body = el('div', null)
  menuBox.appendChild(body)
  root.appendChild(menuBox)

  let loaded = false
  const onOpen = async () => {
    if (loaded) return
    loaded = true
    body.replaceChildren(el('p', 'muted', t('poi.menu.loading')))
    try {
      const res = await fetch(`/api/v1/poi/${encodeURIComponent(poi.id)}/menu?lang=${lang}`)
      if (!res.ok) throw new Error(String(res.status))
      const { items } = await res.json()
      if (!items.length) { body.replaceChildren(el('p', 'muted', t('poi.menu.empty'))); return }
      const ul = el('ul')
      for (const it of items) {
        const { main, sub } = menuItemLabel(it)
        const li = el('li')
        const name = el('span', 'mi-name', main)
        if (sub) name.appendChild(el('small', null, sub))
        li.append(name, el('span', 'mi-price', formatPrice(it.price, lang)))
        ul.appendChild(li)
      }
      body.replaceChildren(ul)
    } catch {
      loaded = false // lần mở sau thử lại
      body.replaceChildren(el('p', 'muted', t('poi.menu.empty')))
    }
  }
  return { root, onOpen }
}
