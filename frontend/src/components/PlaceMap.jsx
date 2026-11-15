import { useEffect } from "react";
import { CircleMarker, MapContainer, Polyline, TileLayer, Tooltip, ZoomControl, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";

// Show every place until a route is chosen, then zoom to that route (room for its labels).
function FitView({ places, route }) {
  const map = useMap();
  const target = route.length === 2 ? route : places;
  const key = target.map((p) => p.id).join(",");
  useEffect(() => {
    if (target.length) {
      // A route gets extra room above and below for its two labels.
      const padding = route.length === 2 ? { paddingTopLeft: [40, 72], paddingBottomRight: [40, 72] } : { padding: [24, 24] };
      map.fitBounds(target.map((p) => [p.lat, p.lng]), padding);
    }
  }, [map, key]); // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}

// Tap a place to choose it. Circle markers avoid Leaflet's image icons, which need extra
// bundler setup.
export default function PlaceMap({ places, fromId, toId, onPick }) {
  const from = places.find((p) => String(p.id) === String(fromId));
  const to = places.find((p) => String(p.id) === String(toId));

  return (
    <div className="map">
      <MapContainer center={[8.53, 76.9]} zoom={12} scrollWheelZoom={false} zoomControl={false}>
        <ZoomControl position="bottomright" />
        {/* Free OpenStreetMap tiles, attribution required. Heavy production traffic
            should use a tile provider (their usage policy limits bulk use). */}
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <FitView places={places} route={[from, to].filter(Boolean)} />
        {from && to && (
          <Polyline
            positions={[[from.lat, from.lng], [to.lat, to.lng]]}
            pathOptions={{ color: "#0f766e", weight: 4, dashArray: "6 8" }}
          />
        )}
        {places.map((p) => {
          const selected = p === from || p === to;
          return (
            <CircleMarker
              key={p.id}
              center={[p.lat, p.lng]}
              radius={selected ? 9 : 6}
              pathOptions={{
                color: "#ffffff",
                weight: 2,
                fillOpacity: 1,
                fillColor: p.kind === "station" ? "#0f766e" : selected ? "#17201d" : "#5d6b66",
              }}
              eventHandlers={{ click: () => onPick?.(String(p.id)) }}
            >
              <Tooltip direction={p === to ? "bottom" : "top"} offset={[0, p === to ? 6 : -6]} permanent={selected}>
                {p.name}
              </Tooltip>
            </CircleMarker>
          );
        })}
      </MapContainer>
    </div>
  );
}
