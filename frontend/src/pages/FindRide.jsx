import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { api } from "../api.js";
import LocationPicker from "../components/LocationPicker.jsx";
import { usePlaces } from "../usePlaces.js";
import { TrustBadges } from "../components/Trust.jsx";
import { VEHICLE_LABEL, formatTime, fromLocalInput, plural, splitFare, toLocalInput } from "../format.js";
import { formatDistance } from "../geo.js";

function TripCard({ trip, message, onJoin }) {
  const share = splitFare(trip);
  return (
    <article className="card trip">
      <div className="trip-head">
        <strong>{formatTime(trip.depart_at)}</strong>
        <span className="pill open plain">{plural(trip.seats_left, "seat")} left</span>
      </div>
      <p className="route">
        {trip.start.label} → {trip.end.label}
      </p>
      <p className="muted">Starts {formatDistance(trip.pickup_distance_m)} from you</p>
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
  const prefill = useLocation().state ?? {};
  const { places, error: placesError } = usePlaces();
  const [from, setFrom] = useState(prefill.from ?? null);
  const [to, setTo] = useState(prefill.to ?? null);
  const [when, setWhen] = useState(() => toLocalInput(new Date()));
  const [trips, setTrips] = useState(null);
  const [page, setPage] = useState({ params: null, next: null }); // for "Load more"
  const [messages, setMessages] = useState({}); // trip id -> result of "Request to join"
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function search(event) {
    event.preventDefault();
    if (!from || !to) {
      setError("Set where you are and where you're going (use your location, or tap the map).");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const params = {
        from_lat: from.lat,
        from_lng: from.lng,
        to_lat: to.lat,
        to_lng: to.lng,
        at: fromLocalInput(when),
        window_minutes: 45,
      };
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
        <LocationPicker places={places} from={from} to={to} onFrom={setFrom} onTo={setTo} />
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
          <p>No rides starting near you for that destination around that time.</p>
          <Link className="button" to="/offer" state={{ from, to, when }}>
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
