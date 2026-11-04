/** Gộp kết quả delta sync vào danh sách POI hiện có. */
export function mergeDelta(current, delta) {
  const removed = new Set(delta.removed_poi_ids || [])
  const byId = new Map(current.filter((p) => !removed.has(p.id)).map((p) => [p.id, p]))
  for (const p of delta.pois || []) byId.set(p.id, p)
  return [...byId.values()]
}
