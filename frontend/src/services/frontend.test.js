import { describe, expect, it } from 'vitest'
import { mergeDelta } from './syncUtils'

describe('mergeDelta', () => {
  it('gộp POI mới/sửa và loại POI bị xoá', () => {
    const cur = [{ id: 'a', name: 'A' }, { id: 'b', name: 'B' }, { id: 'c', name: 'C' }]
    const out = mergeDelta(cur, { pois: [{ id: 'b', name: 'B2' }, { id: 'd', name: 'D' }], removed_poi_ids: ['c'] })
    expect(out.map((p) => p.id).sort()).toEqual(['a', 'b', 'd'])
    expect(out.find((p) => p.id === 'b').name).toBe('B2')
  })
  it('delta rỗng giữ nguyên danh sách', () => {
    const cur = [{ id: 'a' }]
    expect(mergeDelta(cur, {})).toEqual(cur)
  })
})
