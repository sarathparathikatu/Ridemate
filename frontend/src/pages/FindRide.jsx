import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import PlaceMap from "../components/PlaceMap.jsx";
import { DEFAULT_STATION, PlaceSelect, usePlaces } from "../components/PlaceSelect.jsx";
import { TrustBadges } from "../components/Trust.jsx";
import { VEHICLE_LABEL, formatTime, fromLocalInput, plural, splitFare, toLocalInput } from "../format.js";

function TripCard({ trip, message, onJoin }) {
  const share = splitFare(trip);
  return (
    <article className="card trip">
      <div className="trip-head">
        <strong>{formatTime(trip.depart_at)}</strong>
        <span className="pill open plain">{plural(trip.seats_left, "seat")} left</span>
      </div>
      <p className="route">
        {trip.from_place.name} → {trip.to_place.name}
      </p>
      {trip.match === "on_the_way" && (
        <p className="badge-way">
          On the way: drops you first (about {trip.detour_km} km extra for the host)
        </p>
      )}
      <p className="muted">
        Host: {trip.host.display_name} · {VEHICLE_LABEL[trip.vehicle]} · ±{trip.flex_minutes} min
      </p>
      <TrustBadges person={trip.host} />
      {share && (
        <p className="fare">
          ₹{trip.fare_estimate} ride → about ₹{share} each if you join
        </p>
      )}
      {trip.note && <p className="note">“{trip.note}”</p>}
      {message ? (
        <p className="muted">{message}</p>
      ) : (
        <button className="primary" onClick={onJoin}>
          Request to join
        </button>
      )}
    </article>
  );
}

export default function FindRide() {
  const { places, error: placesError } = usePlaces();
  const [fromId, setFromId] = useState("");
  const [toId, setToId] = useState("");
  const [when, setWhen] = useState(() => toLocalInput(new Date()));
  const [trips, setTrips] = useState(null);
  const [page, setPage] = useState({ params: null, next: null }); // for "Load more"
  const [messages, setMessages] = useState({}); // trip id -> result of "Request to join"
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // Default pickup: the station, the whole reason this app exists.
  const station = places.find((p) => p.name === DEFAULT_STATION);
  const pickup = fromId || (station ? String(station.id) : "");

  async function search(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const params = { from_place_id: pickup, to_place_id: toId, at: fromLocalInput(when), window_minutes: 45 };
      const result = await api.searchTrips(params);
      setTrips(result.items);
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
    try {
      await api.requestToJoin(trip.id, 1);
      setMessages((m) => ({ ...m, [trip.id]: "Request sent! Track it under My rides." }));
    } catch (err) {
      setMessages((m) => ({ ...m, [trip.id]: err.message }));
    }
  }

  return (
    <>
      <form className="card form" onSubmit={search}>
        <h1>Find a ride</h1>
        <PlaceMap places={places} fromId={pickup} toId={toId} onPick={(id) => id !== pickup && setToId(id)} />
        <p className="muted hint">Tap a place on the map to choose where you are going.</p>
        <PlaceSelect label="From" places={places} value={pickup} onChange={setFromId} />
        <PlaceSelect label="Going to" places={places} value={toId} onChange={setToId} exclude={pickup} />
        <label>
          Around
          <input type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} required />
        </label>
        {(placesError || error) && <p className="error">{placesError || error}</p>}
        <button className="primary" disabled={busy}>
          {busy ? "Searching…" : "Search"}
        </button>
      </form>

      {trips?.length === 0 && (
        <div className="card empty">
          <p>No rides yet for this route around that time.</p>
          <Link className="button" to="/offer" state={{ fromId: pickup, toId, when }}>
            Offer one so others can join you
          </Link>
        </div>
      )}
      {trips?.map((trip) => (
        <TripCard key={trip.id} trip={trip} message={messages[trip.id]} onJoin={() => join(trip)} />
      ))}
      {page.next && (
        <button className="more" onClick={loadMore} disabled={busy}>
          Load more rides
        </button>
      )}
    </>
  );
}
