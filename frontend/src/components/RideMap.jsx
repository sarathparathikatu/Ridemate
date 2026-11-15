import { useEffect } from "react";
import {
  CircleMarker,
  MapContainer,
  Polyline,
  TileLayer,
  Tooltip,
  ZoomControl,
  useMap,
  useMapEvents,
} from "react-leaflet";
import "leaflet/dist/leaflet.css";

const KERALA = [10.5, 76.3]; // where the map starts before anything is chosen

// Where to look: the route once both ends are set, one end zoomed in, else known places.
function FitView({ suggestions, from, to }) {
  const map = useMap();
  const key = [from && `${from.lat},${from.lng}`, to && `${to.lat},${to.lng}`, suggestions.length].join("|");
  useEffect(() => {
    if (from && to) {
      map.fitBounds([[from.lat, from.lng], [to.lat, to.lng]], { paddingTopLeft: [40, 72], paddingBottomRight: [40, 72] });
    } else if (from || to) {
      const point = from ?? to;
      map.setView([point.lat, point.lng], Math.max(map.getZoom(), 15));
    } else if (suggestions.length) {
      map.fitBounds(suggestions.map((p) => [p.lat, p.lng]), { padding: [24, 24] });
    }
  }, [map, key]); // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}

function TapToPin({ onTap }) {
  useMapEvents({ click: (event) => onTap({ lat: event.latlng.lat, lng: event.latlng.lng }) });
  return null;
}

// suggestions: known places (grey dots). from/to: {lat, lng, label}. Pass onTap to let
// people drop pins, onPickPlace to let them tap a grey dot.
export default function RideMap({ suggestions = [], from, to, onTap, onPickPlace }) {
  return (
    <div className="map">
      <MapContainer center={KERALA} zoom={8} scrollWheelZoom={false} zoomControl={false}>
        <ZoomControl position="bottomright" />
        {/* Free OpenStreetMap tiles, attribution required. Heavy production traffic
            should use a tile provider (their usage policy limits bulk use). */}
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <FitView suggestions={suggestions} from={from} to={to} />
        {onTap && <TapToPin onTap={onTap} />}
        {suggestions.map((place) => (
          <CircleMarker
            key={place.id}
            center={[place.lat, place.lng]}
            radius={5}
            // Tapping a known place must not also drop a pin underneath it.
            bubblingMouseEvents={false}
            pathOptions={{ color: "#ffffff", weight: 1.5, fillOpacity: 0.9, fillColor: "#5d6b66" }}
            eventHandlers={onPickPlace ? { click: () => onPickPlace(place) } : undefined}
          >
            <Tooltip direction="top" offset={[0, -5]}>
              {place.name}
            </Tooltip>
          </CircleMarker>
        ))}
        {from && to && (
          <Polyline
            positions={[[from.lat, from.lng], [to.lat, to.lng]]}
            pathOptions={{ color: "#0f766e", weight: 4, dashArray: "6 8" }}
          />
        )}
        {from && (
          <CircleMarker center={[from.lat, from.lng]} radius={9} interactive={false} pathOptions={{ color: "#ffffff", weight: 2, fillOpacity: 1, fillColor: "#0f766e" }}>
            <Tooltip permanent direction="top" offset={[0, -8]}>
              {from.label}
            </Tooltip>
          </CircleMarker>
        )}
        {to && (
          <CircleMarker center={[to.lat, to.lng]} radius={9} interactive={false} pathOptions={{ color: "#ffffff", weight: 2, fillOpacity: 1, fillColor: "#17201d" }}>
            <Tooltip permanent direction="bottom" offset={[0, 8]}>
              {to.label}
            </Tooltip>
          </CircleMarker>
        )}
      </MapContainer>
    </div>
  );
}
