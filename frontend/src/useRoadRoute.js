import { useEffect, useState } from "react";
import { api } from "./api.js";

// The road route between two points: { distance_m, duration_s, points }.
// Returns null while it loads and when the map service can't be reached; the map then
// draws a simple curve instead, so the route is a nice extra and never a blocker.
export function useRoadRoute(from, to) {
  const [found, setFound] = useState({ key: null, route: null });
  // ~11 m precision, the same rounding the API uses: tiny pin nudges reuse the answer.
  const key =
    from && to ? [from.lat, from.lng, to.lat, to.lng].map((n) => Number(n).toFixed(4)).join(",") : null;

  useEffect(() => {
    if (!key) return undefined;
    let stale = false;
    // A short pause: while someone taps around choosing a spot, only the last pair is fetched.
    const timer = setTimeout(() => {
      api
        .roadRoute(from, to)
        .then((route) => !stale && setFound({ key, route }))
        .catch(() => {});
    }, 350);
    return () => {
      stale = true; // an answer for an older pair of points must not overwrite a newer one
      clearTimeout(timer);
    };
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps

  return found.key === key ? found.route : null;
}

// "2.1 km · about 4 min by road"
export function describeRoute(route) {
  const km = route.distance_m < 1000 ? `${Math.round(route.distance_m / 10) * 10} m` : `${(route.distance_m / 1000).toFixed(1)} km`;
  return `${km} · about ${Math.max(1, Math.round(route.duration_s / 60))} min by road`;
}
