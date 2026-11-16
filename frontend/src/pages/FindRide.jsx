import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import { VehicleArt } from "../components/Art.jsx";
import Icon from "../components/Icon.jsx";
import { PlaceChips, RouteFields, useRoutePicker } from "../components/LocationPicker.jsx";
import MapShell from "../components/MapShell.jsx";
import RideMap from "../components/RideMap.jsx";
import { TrustBadges } from "../components/Trust.jsx";
import { Avatar, EmptyState, Notice, RouteLine, SkeletonCards } from "../components/ui.jsx";
import {
  VEHICLE_LABEL,
  formatClock,
  formatDay,
  fromLocalInput,
  plural,
  splitFare,
  toLocalInput,
} from "../format.js";
import { formatDistance } from "../geo.js";
import { usePlaces } from "../usePlaces.js";

const TIME_PRESETS = [
  { id: "now", label: "Now", minutes: 0 },
  { id: "15", label: "15 min", minutes: 15 },
  { id: "30", label: "30 min", minutes: 30 },
  { id: "60", label: "1 hour", minutes: 60 },
];

// A preset as a datetime-local value, counted from this moment.
function presetTime(id) {
  const minutes = TIME_PRESETS.find((p) => p.id === id)?.minutes ?? 0;
  return toLocalInput(new Date(Date.now() + minutes * 60000));
}

function greeting() {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

// One ride in the list, laid out like a ride app's options: vehicle, details, price.
function RideOption({ trip, selected, message, onSelect }) {
  const share = splitFare(trip);
  const day = formatDay(trip.depart_at);
  return (
    <article className={`option ${selected ? "selected" : ""}`}>
      <button type="button" className="option-main" aria-pressed={selected} onClick={onSelect}>
        <VehicleArt vehicle={trip.vehicle} width={68} />
        <span className="option-text">
          <span className="option-title">
            {formatClock(trip.depart_at)}
            <span className="option-seats">
              <Icon name="users" size={14} />
              {trip.seats_left}
            </span>
          </span>
          <span className="option-sub">
            {day !== "Today" && `${day} · `}
            {formatDistance(trip.pickup_distance_m)} away · {VEHICLE_LABEL[trip.vehicle]}
          </span>
          <span className="option-host">
            <Avatar name={trip.host.display_name} size="xs" />
            {trip.host.display_name}
          </span>
        </span>
        <span className="option-price">
          {share ? (
            <>
              <strong>₹{share}</strong>
              <span>per person</span>
            </>
          ) : (
            <span>Fare at pickup</span>
          )}
        </span>
      </button>

      {selected && (
        <div className="option-detail">
          {trip.match === "on_the_way" && (
            <p className="badge-way">
              <Icon name="rides" size={16} />
              On the way: drops you first (about {trip.detour_km} km extra for the host)
            </p>
          )}
          <RouteLine from={trip.start.label} to={trip.end.label} />
          <div className="meta">
            <span>
              <Icon name="users" size={16} />
              {plural(trip.seats_left, "seat")} left
            </span>
            <span>
              <Icon name="clock" size={16} />
              waits ±{trip.flex_minutes} min
            </span>
            {share && (
              <span>
                <Icon name="wallet" size={16} />₹{trip.fare_estimate} ride
              </span>
            )}
          </div>
          <div className="host-line">
            <span className="muted small-text">Hosted by {trip.host.display_name}</span>
            <TrustBadges person={trip.host} />
          </div>
          {trip.note && <p className="note">“{trip.note}”</p>}
          {message && <Notice kind={message.ok ? "success" : "error"}>{message.text}</Notice>}
        </div>
      )}
    </article>
  );
}

function Promo() {
  return (
    <div className="promo">
      <div>
        <strong>One auto. Three riders. A third of the fare.</strong>
        <p>A ₹150 ride shared by three is ₹50 each.</p>
      </div>
      <VehicleArt vehicle="auto" width={92} />
    </div>
  );
}

function HowItWorks() {
  const steps = [
    { title: "Set your route", text: "From the station to where you're going." },
    { title: "Join a co-traveller", text: "Contacts are shared only after the host accepts." },
    { title: "Split the fare", text: "One ride, one fare. Pay the driver directly." },
  ];
  return (
    <ol className="howto">
      {steps.map((step, i) => (
        <li key={step.title}>
          <span className="howto-num">{i + 1}</span>
          <div>
            <strong>{step.title}</strong>
            <p className="muted small-text">{step.text}</p>
          </div>
        </li>
      ))}
    </ol>
  );
}

export default function FindRide() {
  const { user } = useAuth();
  const prefill = useLocation().state ?? {};
  const { places, error: placesError } = usePlaces();
  const [from, setFrom] = useState(prefill.from ?? null);
  const [to, setTo] = useState(prefill.to ?? null);
  const [when, setWhen] = useState(() => toLocalInput(new Date()));
  const [preset, setPreset] = useState("now");
  const [trips, setTrips] = useState(null); // null = still planning the route
  const [selectedId, setSelectedId] = useState(null);
  const [page, setPage] = useState({ params: null, next: null }); // for "Load more"
  const [messages, setMessages] = useState({}); // trip id -> {text, ok} after "Request to join"
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const picker = useRoutePicker({ places, from, to, onFrom: setFrom, onTo: setTo });

  function choosePreset(id) {
    setPreset(id);
    if (id !== "custom") setWhen(presetTime(id));
  }

  async function search(event) {
    event.preventDefault();
    if (!from || !to) {
      setError("Set where you are and where you're going (use your location, or tap the map).");
      return;
    }
    setBusy(true);
    setError("");
    try {
      // "Now" means the moment you press the button, not when the page opened.
      const at = preset === "custom" ? when : presetTime(preset);
      const params = {
        from_lat: from.lat,
        from_lng: from.lng,
        to_lat: to.lat,
        to_lng: to.lng,
        at: fromLocalInput(at),
        window_minutes: 45,
      };
      const result = await api.searchTrips(params);
      setTrips(result.items);
      setSelectedId(result.items[0]?.id ?? null);
      setPage({ params, next: result.next_cursor });
      setMessages({});
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function loadMore() {
    setBusy(true);
    try {
      const result = await api.searchTrips({ ...page.params, cursor: page.next });
      setTrips((current) => [...current, ...result.items]);
      setPage((p) => ({ ...p, next: result.next_cursor }));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function join(trip) {
    setBusy(true);
    try {
      await api.requestToJoin(trip.id, 1);
      setMessages((m) => ({
        ...m,
        [trip.id]: { ok: true, text: `Request sent. You'll get an alert when ${trip.host.display_name} answers.` },
      }));
    } catch (err) {
      setMessages((m) => ({ ...m, [trip.id]: { ok: false, text: err.message } }));
    } finally {
      setBusy(false);
    }
  }

  const planning = trips === null;
  const selected = trips?.find((trip) => trip.id === selectedId) ?? null;
  const selectedShare = selected ? splitFare(selected) : null;
  let timeLabel = "Leaving now";
  if (preset === "custom") timeLabel = `${formatDay(when)}, ${formatClock(when)}`;
  else if (preset !== "now") timeLabel = `Leaving in ${TIME_PRESETS.find((p) => p.id === preset).label}`;

  const map = (
    <RideMap
      fill
      suggestions={planning ? places : []}
      from={from}
      to={to}
      rides={trips ?? []}
      selectedRideId={selectedId}
      onTap={planning ? picker.tap : undefined}
      onPickPlace={picker.pickPlace}
      onSelectRide={setSelectedId}
    />
  );

  if (planning) {
    return (
      <MapShell map={map}>
        <div>
          <p className="eyebrow">
            {greeting()}, {user.display_name.split(" ")[0]}
          </p>
          <h1 className="sheet-title">Where to?</h1>
        </div>
        <form className="form" onSubmit={search}>
          <RouteFields picker={picker} from={from} to={to} onFrom={setFrom} onTo={setTo} />
          <PlaceChips places={places} picker={picker} />
          <div className="field">
            <span className="field-label">
              <Icon name="clock" size={16} /> Leaving
            </span>
            <div className="chips">
              {TIME_PRESETS.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={preset === item.id ? "chip on" : "chip"}
                  aria-pressed={preset === item.id}
                  onClick={() => choosePreset(item.id)}
                >
                  {item.label}
                </button>
              ))}
              <button
                type="button"
                className={preset === "custom" ? "chip on" : "chip"}
                aria-pressed={preset === "custom"}
                onClick={() => choosePreset("custom")}
              >
                <Icon name="calendar" size={14} /> Pick a time
              </button>
            </div>
            {preset === "custom" && (
              <input
                type="datetime-local"
                aria-label="Leaving around"
                value={when}
                onChange={(e) => setWhen(e.target.value)}
                required
              />
            )}
          </div>
          {(placesError || error) && <p className="error">{placesError || error}</p>}
          <div className="sheet-cta">
            <button className="cta" disabled={busy}>
              {busy ? "Searching…" : "Find rides"}
            </button>
          </div>
        </form>
        <Promo />
        <HowItWorks />
      </MapShell>
    );
  }

  return (
    <MapShell map={map}>
      <div className="sheet-head">
        <button type="button" className="round-button" onClick={() => setTrips(null)} aria-label="Edit route" title="Edit route">
          <Icon name="back" />
        </button>
        <div className="trip-summary">
          <strong>
            {from.label} <Icon name="arrow" size={14} /> {to.label}
          </strong>
          <span className="muted small-text">{timeLabel}</span>
        </div>
      </div>

      {trips.length === 0 ? (
        <EmptyState
          art={<VehicleArt vehicle="auto" width={120} />}
          title="No rides yet on this route"
          text="Nobody nearby is going your way around that time. Be the host: offer the ride and others from your train can join you."
        >
          <Link className="button cta" to="/offer" state={{ from, to, when }}>
            Offer this ride
          </Link>
        </EmptyState>
      ) : (
        <>
          <h2 className="sheet-subtitle">
            {trips.length}
            {page.next ? "+" : ""} {trips.length === 1 && !page.next ? "ride" : "rides"} going your way
          </h2>
          <div className="options">
            {trips.map((trip) => (
              <RideOption
                key={trip.id}
                trip={trip}
                selected={trip.id === selectedId}
                message={messages[trip.id]}
                onSelect={() => setSelectedId(trip.id)}
              />
            ))}
          </div>
          {busy && page.next && <SkeletonCards count={1} />}
          {page.next && (
            <button type="button" className="more" onClick={loadMore} disabled={busy}>
              {busy ? "Loading…" : "Load more rides"}
            </button>
          )}
          {error && <p className="error">{error}</p>}
          {selected && (
            <div className="sheet-cta">
              {messages[selected.id]?.ok ? (
                <Link className="button cta" to="/rides">
                  Track it in Activity
                  <Icon name="arrow" size={18} />
                </Link>
              ) : (
                <button type="button" className="cta" disabled={busy} onClick={() => join(selected)}>
                  Request to join{selectedShare ? ` · ₹${selectedShare}` : ""}
                </button>
              )}
            </div>
          )}
        </>
      )}
    </MapShell>
  );
}
