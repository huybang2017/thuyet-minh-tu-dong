const EARTH_RADIUS_METERS = 6371000

export function distanceMeters(from, poi) {
  const toRadians = (degrees) => degrees * Math.PI / 180
  const dLat = toRadians(poi.lat - from.lat)
  const dLng = toRadians(poi.lng - from.lng)
  const lat1 = toRadians(from.lat)
  const lat2 = toRadians(poi.lat)
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2
  return 2 * EARTH_RADIUS_METERS * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
}

export function searchPois(pois, { query = '', radius = 'any', origin = null } = {}) {
  const term = query.trim().toLocaleLowerCase()
  return pois
    .map((poi) => ({ poi, distance: origin ? distanceMeters(origin, poi) : null }))
    .filter(({ poi, distance }) => {
      const matchesQuery = !term || [poi.name, poi.description, poi.address].some((value) => value?.toLocaleLowerCase().includes(term))
      const matchesRadius = radius === 'any' || (distance !== null && distance <= Number(radius))
      return matchesQuery && matchesRadius
    })
    .sort((a, b) => a.distance !== null && b.distance !== null ? a.distance - b.distance : a.poi.name.localeCompare(b.poi.name))
    .map(({ poi, distance }) => ({ ...poi, distance }))
}
