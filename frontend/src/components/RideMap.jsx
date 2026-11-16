import L from "leaflet";
import { useEffect, useRef } from "react";
import {
  AttributionControl,
  CircleMarker,
  MapContainer,
  Marker,
  Polyline,
  TileLayer,
  Tooltip,
  ZoomControl,
  useMap,
  useMapEvents,
} from "react-leaflet";
import "leaflet/dist/leaflet.css";

const KERALA = [10.5, 76.3]; // where the map starts before anything is chosen
const INK = "#0b0b0c";
const LIME = "#c6f135";

// Pins are plain HTML styled in CSS (.pin-from is a ring, .pin-to a square).
const pin = (kind) => L.divIcon({ className: `pin pin-${kind}`, iconSize: [22, 22], iconAnchor: [11, 11] });
const FROM_PIN = pin("from");
const TO_PIN = pin("to");

// In "fill" mode the map is the page background and part of it is covered: the sheet over
// the lower half on a phone, the panel on the left on a laptop. Padding keeps what matters
// inside the part you can actually see.
function visiblePadding(fill) {
  if (!fill) return { paddingTopLeft: [40, 56], paddingBottomRight: [40, 56] };
  if (window.matchMedia("(min-width: 960px)").matches) {
    return { paddingTopLeft: [540, 80], paddingBottomRight: [80, 80] };
  }
  return { paddingTopLeft: [40, 96], paddingBottomRight: [40, Math.round(window.innerHeight * 0.58) + 28] };
}

// Where to look: the route once both ends are set, one end zoomed in, else known places.
function FitView({ suggestions, from, to, rides, fill }) {
  const map = useMap();
  const key = [
    from && `${from.lat},${from.lng}`,
    to && `${to.lat},${to.lng}`,
    suggestions.length,
    rides.map((r) => r.id).join(","),
  ].join("|");
  const moved = useRef(false);
  useEffect(() => {
    const padding = visiblePadding(fill);
    // The first view appears instantly; later ones glide there. flyToBounds matters for
    // correctness too: it cancels a move already in progress, whereas fitBounds silently
    // ignores a request made while a zoom animation is running (e.g. the GPS position
    // arriving just as the map zooms to the known places).
    const show = (bounds, options) => {
      if (moved.current) map.flyToBounds(bounds, { ...padding, ...options, duration: 0.6 });
      else map.fitBounds(bounds, { ...padding, ...options, animate: false });
      moved.current = true;
    };
    const ends = [from, to].filter(Boolean).map((p) => [p.lat, p.lng]);
    if (ends.length === 2) {
      show([...ends, ...rides.map((r) => [r.start.lat, r.start.lng])], { maxZoom: 16 });
    } else if (ends.length === 1) {
      show([ends[0], ends[0]], { maxZoom: Math.max(Math.round(map.getZoom()), 15) });
    } else if (suggestions.length) {
      show(suggestions.map((p) => [p.lat, p.lng]), {});
    }
  }, [map, key]); // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}

function TapToPin({ onTap }) {
  useMapEvents({ click: (event) => onTap({ lat: event.latlng.lat, lng: event.latlng.lng }) });
  return null;
}

// A gentle arc between the two ends. We don't know the real road route, so a curve says
// "from here to there" without pretending to be turn-by-turn directions.
function arc(a, b, steps = 24) {
  const bend = 0.16;
  const cLat = (a.lat + b.lat) / 2 + (b.lng - a.lng) * bend;
  const cLng = (a.lng + b.lng) / 2 - (b.lat - a.lat) * bend;
  return Array.from({ length: steps + 1 }, (_, i) => {
    const t = i / steps;
    const u = 1 - t;
    return [u * u * a.lat + 2 * u * t * cLat + t * t * b.lat, u * u * a.lng + 2 * u * t * cLng + t * t * b.lng];
  });
}

// suggestions: known places (grey dots). from/to: {lat, lng, label}. rides: search results
// shown as lime pins. Pass onTap to let people drop pins, onPickPlace to let them tap a
// grey dot, onSelectRide to let them tap a ride. fill: the map is the page background.
export default function RideMap({
  suggestions = [],
  from,
  to,
  rides = [],
  selectedRideId,
  onTap,
  onPickPlace,
  onSelectRide,
  fill = false,
}) {
  const route = from && to ? arc(from, to) : null;
  return (
    <div className={fill ? "map map-fill" : "map"}>
      <MapContainer center={KERALA} zoom={8} scrollWheelZoom={fill} zoomControl={false} attributionControl={false}>
        <ZoomControl position={fill ? "topright" : "bottomright"} />
        <AttributionControl position="bottomright" prefix={false} />
        {/* Free OpenStreetMap tiles, attribution required. Heavy production traffic
            should use a tile provider (their usage policy limits bulk use). */}
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <FitView suggestions={suggestions} from={from} to={to} rides={rides} fill={fill} />
        {onTap && <TapToPin onTap={onTap} />}
        {suggestions.map((place) => (
          <CircleMarker
            key={place.id}
            center={[place.lat, place.lng]}
            radius={5}
            // Tapping a known place must not also drop a pin underneath it.
            bubblingMouseEvents={false}
            pathOptions={{ color: "#ffffff", weight: 1.5, fillOpacity: 0.9, fillColor: "#6b6b6b" }}
            eventHandlers={onPickPlace ? { click: () => onPickPlace(place) } : undefined}
          >
            <Tooltip direction="top" offset={[0, -5]}>
              {place.name}
            </Tooltip>
          </CircleMarker>
        ))}
        {route && (
          <>
            <Polyline positions={route} interactive={false} pathOptions={{ color: "#ffffff", weight: 9, opacity: 0.9 }} />
            <Polyline positions={route} interactive={false} pathOptions={{ color: INK, weight: 4.5 }} />
          </>
        )}
        {rides.map((ride) => (
          <CircleMarker
            key={`ride-${ride.id}`}
            center={[ride.start.lat, ride.start.lng]}
            radius={ride.id === selectedRideId ? 11 : 7}
            bubblingMouseEvents={false}
            pathOptions={{ color: INK, weight: 2.5, fillOpacity: 1, fillColor: LIME }}
            eventHandlers={onSelectRide ? { click: () => onSelectRide(ride.id) } : undefined}
          >
            <Tooltip direction="top" offset={[0, -8]}>
              Ride from {ride.start.label}
            </Tooltip>
          </CircleMarker>
        ))}
        {from && (
          <Marker position={[from.lat, from.lng]} icon={FROM_PIN} interactive={false} keyboard={false}>
            <Tooltip permanent direction="top" offset={[0, -12]} className="map-label">
              {from.label}
            </Tooltip>
          </Marker>
        )}
        {to && (
          <Marker position={[to.lat, to.lng]} icon={TO_PIN} interactive={false} keyboard={false}>
            <Tooltip permanent direction="bottom" offset={[0, 12]} className="map-label">
              {to.label}
            </Tooltip>
          </Marker>
        )}
      </MapContainer>
    </div>
  );
}
