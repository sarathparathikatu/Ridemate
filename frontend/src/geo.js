// Distances on the Earth's surface (haversine), matching the backend's calculation.
export function distanceM(a, b) {
  const R = 6371000;
  const rad = (d) => (d * Math.PI) / 180;
  const dLat = rad(b.lat - a.lat);
  const dLng = rad(b.lng - a.lng);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

export function formatDistance(meters) {
  return meters < 1000 ? `${Math.round(meters / 10) * 10} m` : `${(meters / 1000).toFixed(1)} km`;
}

// A friendly name for a pin: "Near Kulathoor" when a known place is close, else `fallback`.
export function describePoint(point, places, fallback) {
  let best = null;
  for (const place of places) {
    const d = distanceM(point, place);
    if (d <= 600 && (!best || d < best.d)) best = { name: place.name, d };
  }
  if (!best) return fallback;
  return best.d < 60 ? best.name : `Near ${best.name}`;
}
