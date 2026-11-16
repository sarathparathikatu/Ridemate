import { useRef, useState } from "react";
import { api } from "../api.js";
import { describePoint } from "../geo.js";
import Icon from "./Icon.jsx";

// Choosing a pickup and a destination anywhere: GPS, a tap on the map, or a known place.
// The logic lives in this hook so the page can wire it to both the form and the map.
export function useRoutePicker({ places, from, to, onFrom, onTo }) {
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

  function swap() {
    onFrom(to);
    onTo(from);
  }

  function locate() {
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

  return { active, setActive, gps, tap, pickPlace, swap, locate };
}

function Slot({ kind, name, placeholder, point, active, onActivate }) {
  return (
    <button type="button" className={`slot ${active ? "active" : ""}`} aria-pressed={active} onClick={onActivate}>
      <span className={`slot-dot ${kind}`} />
      <span className="slot-text">
        <span className="slot-name">{name}</span>
        <span className={`slot-value ${point ? "" : "empty"}`}>{point ? point.label : placeholder}</span>
      </span>
    </button>
  );
}

// The "Pickup / Where to?" box. editableLabels lets a host name the spots ("Main exit").
export function RouteFields({ picker, from, to, onFrom, onTo, editableLabels = false }) {
  const { active, setActive, gps, swap, locate } = picker;
  return (
    <div className="picker">
      <div className="route-box">
        <div className="route-slots">
          <Slot
            kind="from"
            name="Pickup"
            placeholder="Set your pickup"
            point={from}
            active={active === "from"}
            onActivate={() => setActive("from")}
          />
          <span className="route-connector" aria-hidden="true" />
          <Slot
            kind="to"
            name="Where to?"
            placeholder="Choose a destination"
            point={to}
            active={active === "to"}
            onActivate={() => setActive("to")}
          />
        </div>
        <div className="route-tools">
          <button
            type="button"
            className="round-button"
            onClick={locate}
            disabled={gps.busy}
            aria-label="Use my location"
            title="Use my location"
          >
            <Icon name="locate" className={gps.busy ? "spin" : ""} />
          </button>
          <button
            type="button"
            className="round-button"
            onClick={swap}
            disabled={!from && !to}
            aria-label="Swap pickup and destination"
            title="Swap"
          >
            <Icon name="swap" />
          </button>
        </div>
      </div>

      {gps.error && <p className="error">{gps.error}</p>}

      {editableLabels && (from || to) && (
        <div className="row">
          {from && (
            <label>
              <span className="field-label">Pickup name shown to others</span>
              <input value={from.label} maxLength={120} onChange={(e) => onFrom({ ...from, label: e.target.value })} />
            </label>
          )}
          {to && (
            <label>
              <span className="field-label">Drop name shown to others</span>
              <input value={to.label} maxLength={120} onChange={(e) => onTo({ ...to, label: e.target.value })} />
            </label>
          )}
        </div>
      )}

      <p className="hint">
        <Icon name="pin" size={16} />
        <span>
          Tap the map to set <strong>{active === "from" ? "your pickup" : "your destination"}</strong>, or search for
          it below.
        </span>
      </p>
    </div>
  );
}

// Type a place or an address ("Mavoor Road") and pick from the matches.
// It searches when asked (Enter or the button), not on every keystroke: the free
// OpenStreetMap search service doesn't allow search-as-you-type.
export function PlaceSearch({ picker, near }) {
  const [text, setText] = useState("");
  const [state, setState] = useState({ busy: false, results: null, error: "" });
  const box = useRef(null);
  const what = picker.active === "from" ? "pickup" : "destination";

  async function search() {
    const q = text.trim();
    if (q.length < 3) {
      setState({ busy: false, results: null, error: "Type at least 3 letters." });
      return;
    }
    setState({ busy: true, results: null, error: "" });
    // On a phone the matches would appear under the pinned button: bring the box to the top.
    box.current?.scrollIntoView({ block: "start", behavior: "smooth" });
    try {
      setState({ busy: false, results: await api.searchPlaces(q, near), error: "" });
    } catch (err) {
      setState({ busy: false, results: null, error: `${err.message} You can still tap the map.` });
    }
  }

  function choose(place) {
    picker.pickPlace({ lat: place.lat, lng: place.lng, name: place.label });
    setText("");
    setState({ busy: false, results: null, error: "" });
    // Back to the top, where the map shows the new pin. The page scrolls on a phone, the
    // panel scrolls on a laptop; asking both is harmless.
    window.scrollTo({ top: 0, behavior: "smooth" });
    box.current?.closest(".sheet")?.scrollTo({ top: 0, behavior: "smooth" });
  }

  return (
    <div className="place-search" ref={box}>
      <div className="place-search-row">
        <input
          type="search"
          value={text}
          maxLength={100}
          enterKeyHint="search"
          placeholder={`Search a ${what}: place or address`}
          aria-label={`Search for a ${what} by place or address`}
          onChange={(e) => setText(e.target.value)}
          // This box sits inside the ride form: Enter must search, not submit that form.
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              search();
            }
          }}
        />
        <button type="button" className="round-button" onClick={search} disabled={state.busy} aria-label="Search places">
          <Icon name="search" />
        </button>
      </div>
      {state.busy && <p className="muted small-text">Searching…</p>}
      {state.error && <p className="error">{state.error}</p>}
      {state.results?.length === 0 && (
        <p className="muted small-text">No places found. Try a nearby landmark, or tap the map.</p>
      )}
      {state.results?.length > 0 && (
        <ul className="search-results" aria-label={`Places matching your search: choose your ${what}`}>
          {state.results.map((place) => (
            <li key={`${place.lat},${place.lng}`}>
              <button type="button" className="search-result" onClick={() => choose(place)}>
                <span className="place-chip-icon">
                  <Icon name="pin" size={16} />
                </span>
                <span className="search-result-text">
                  <strong>{place.label}</strong>
                  <span>{place.detail}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// Known places as a row you can swipe through: one tap sets the active field.
export function PlaceChips({ places, picker }) {
  if (places.length === 0) return null;
  return (
    <div className="place-chips" role="group" aria-label={`Known places: sets ${picker.active === "from" ? "your pickup" : "your destination"}`}>
      {places.map((place) => (
        <button key={place.id} type="button" className="place-chip" onClick={() => picker.pickPlace(place)}>
          <span className="place-chip-icon">
            <Icon name={place.kind === "station" ? "train" : "pin"} size={16} />
          </span>
          {place.name}
        </button>
      ))}
    </div>
  );
}
