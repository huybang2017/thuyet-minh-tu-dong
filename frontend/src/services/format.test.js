import { describe, expect, it } from 'vitest'
import { formatPrice, menuItemLabel } from './format'

describe('formatPrice', () => {
  it('định dạng VND, không có phần lẻ', () => {
    const s = formatPrice(65000, 'vi')
    expect(s).toMatch(/65[.,\s ]000/)
    expect(s).toContain('₫')
    expect(formatPrice(65000, 'en')).toMatch(/65,000/)
  })
  it('giá trống/không hợp lệ → chuỗi rỗng', () => {
    expect(formatPrice(null)).toBe('')
    expect(formatPrice('abc')).toBe('')
  })
})

describe('menuItemLabel', () => {
  it('bản dịch làm tên chính, tên gốc làm phụ', () => {
    expect(menuItemLabel({ name: 'Chè bưởi', name_translated: 'Pomelo sweet soup' }))
      .toEqual({ main: 'Pomelo sweet soup', sub: 'Chè bưởi' })
  })
  it('không có bản dịch hoặc bản dịch trùng tên gốc → chỉ hiện tên gốc', () => {
    expect(menuItemLabel({ name: 'Chè bưởi', name_translated: null })).toEqual({ main: 'Chè bưởi', sub: '' })
    expect(menuItemLabel({ name: 'Pho', name_translated: ' pho ' })).toEqual({ main: 'Pho', sub: '' })
  })
})
