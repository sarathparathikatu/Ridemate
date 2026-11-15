import { useState } from "react";
import { describePoint } from "../geo.js";
import RideMap from "./RideMap.jsx";

function Slot({ name, point, active, onActivate, onRename }) {
  return (
    <div className={`slot ${active ? "active" : ""}`}>
      <button type="button" className="slot-button" aria-pressed={active} onClick={onActivate}>
        <span className="slot-name">{name}</span>
        <span className="slot-value">{point ? point.label : "Not set yet"}</span>
      </button>
      {onRename && point && (
        <input
          aria-label={`${name}: name shown to others`}
          value={point.label}
          maxLength={120}
          onChange={(e) => onRename(e.target.value)}
        />
      )}
    </div>
  );
}

// Choose a pickup and a destination anywhere: GPS, a tap on the map, a known place
// (grey dot), or the list. editableLabels lets a host name the spots ("Main exit").
export default function LocationPicker({ places, from, to, onFrom, onTo, editableLabels = false }) {
  const [active, setActive] = useState(from ? "to" : "from");
  const [gps, setGps] = useState({ busy: false, error: "" });

  function put(slot, point) {
    if (slot === "from") {
      onFrom(point);
      setActive("to");
    } else {
      onTo(point);
    }
  }

  function tap(latlng) {
    put(active, { ...latlng, label: describePoint(latlng, places, active === "from" ? "Pickup point" : "Drop point") });
  }

  function pickPlace(place) {
    put(active, { lat: place.lat, lng: place.lng, label: place.name });
  }

  function useMyLocation() {
    if (!("geolocation" in navigator)) {
      setGps({ busy: false, error: "This browser can't share its location. Tap the map instead." });
      return;
    }
    setGps({ busy: true, error: "" });
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const point = { lat: position.coords.latitude, lng: position.coords.longitude };
        put("from", { ...point, label: describePoint(point, places, "My location") });
        setGps({ busy: false, error: "" });
      },
      // Denied, no signal, or switched off by the device owner (e.g. a work laptop).
      () => setGps({ busy: false, error: "Couldn't get your location. Tap the map to set your pickup instead." }),
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 },
    );
  }

  function choose(slot, placeId) {
    const place = places.find((p) => String(p.id) === placeId);
    if (place) put(slot, { lat: place.lat, lng: place.lng, label: place.name });
  }

  return (
    <div className="picker">
      <div className="slots">
        <Slot
          name="From"
          point={from}
          active={active === "from"}
          onActivate={() => setActive("from")}
          onRename={editableLabels ? (label) => onFrom({ ...from, label }) : null}
        />
        <button type="button" className="small" onClick={useMyLocation} disabled={gps.busy}>
          {gps.busy ? "Finding you…" : "Use my location"}
        </button>
        <Slot
          name="Going to"
          point={to}
          active={active === "to"}
          onActivate={() => setActive("to")}
          onRename={editableLabels ? (label) => onTo({ ...to, label }) : null}
        />
      </div>
      <p className="muted hint">
        Tap the map to set {active === "from" ? "your pickup" : "where you're going"}, or tap a grey dot for a known place.
      </p>
      {gps.error && <p className="error">{gps.error}</p>}
      <RideMap suggestions={places} from={from} to={to} onTap={tap} onPickPlace={pickPlace} />
      <details className="list-choice">
        <summary>Or choose known places from a list</summary>
        <label>
          From
          <select value="" onChange={(e) => choose("from", e.target.value)}>
            <option value="">Choose…</option>
            {places.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </label>
        <label>
          Going to
          <select value="" onChange={(e) => choose("to", e.target.value)}>
            <option value="">Choose…</option>
            {places.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </label>
      </details>
    </div>
  );
}
