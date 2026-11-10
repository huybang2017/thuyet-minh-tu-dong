const LOCALE = { vi: 'vi-VN', en: 'en-US', zh: 'zh-CN', ja: 'ja-JP', ko: 'ko-KR' }

/** 65000 → "65.000 ₫" (theo locale của ngôn ngữ đang chọn). */
export function formatPrice(price, lang = 'vi') {
  if (price == null || Number.isNaN(Number(price))) return ''
  return new Intl.NumberFormat(LOCALE[lang] || 'vi-VN', { style: 'currency', currency: 'VND', maximumFractionDigits: 0 })
    .format(Number(price))
}

/** Tên món cho du khách: bản dịch làm chính, tên gốc tiếng Việt làm phụ (để chỉ cho người bán). */
export function menuItemLabel(item) {
  const tr = item.name_translated?.trim()
  if (!tr || tr.toLowerCase() === item.name.trim().toLowerCase()) return { main: item.name, sub: '' }
  return { main: tr, sub: item.name }
}
