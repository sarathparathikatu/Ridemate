import { useCallback, useEffect, useState } from "react";
import { api } from "../api.js";
import Contact from "../components/Contact.jsx";
import { RatePerson, SafetyActions, ShareButton } from "../components/Trust.jsx";
import { VEHICLE_LABEL, formatTime, plural, splitFare } from "../format.js";
import { NotificationPrompt, useLiveEvents } from "../live.jsx";

const isActive = (trip) => trip.status === "open" || trip.status === "full";
// The host can close the ride from 30 minutes before departure (the API enforces it too).
const hasStarted = (trip) => new Date(trip.depart_at) <= new Date(Date.now() + 30 * 60000);

function StatusPill({ status }) {
  return <span className={`pill ${status}`}>{status}</span>;
}

function HostedTrip({ trip, version, onChange }) {
  const [requests, setRequests] = useState([]);
  const [error, setError] = useState("");
  const active = isActive(trip);

  const loadRequests = useCallback(
    () => api.tripRequests(trip.id).then(setRequests).catch((err) => setError(err.message)),
    [trip.id],
  );
  // `version` changes on every Refresh: React keeps this card mounted (same key), so
  // without it the card would never re-fetch and new requests would stay invisible.
  const completed = trip.status === "completed";
  useEffect(() => {
    if (active || completed) loadRequests();
  }, [active, completed, loadRequests, version]);

  async function act(action) {
    setError("");
    try {
      await action();
      await loadRequests();
      onChange();
    } catch (err) {
      setError(err.message);
    }
  }

  const pending = requests.filter((r) => r.status === "pending");
  const accepted = requests.filter((r) => r.status === "accepted");

  return (
    <article className="card trip">
      <div className="trip-head">
        <strong>{formatTime(trip.depart_at)}</strong>
        <StatusPill status={trip.status} />
      </div>
      <p className="route">
        {trip.start.label} → {trip.end.label}
      </p>
      <p className="muted">
        {trip.seats_taken}/{trip.seats_total} seats taken · {VEHICLE_LABEL[trip.vehicle]}
      </p>

      {accepted.length > 0 && (
        <div className="people">
          <h3>Riding with you</h3>
          {accepted.map((r) =>
            completed ? (
              <RatePerson key={r.id} tripId={trip.id} person={r.requester_contact} />
            ) : (
              <div key={r.id}>
                <Contact person={r.requester_contact} extra={plural(r.seats, "seat")} />
                <SafetyActions userId={r.requester_contact.id} tripId={trip.id} />
              </div>
            ),
          )}
        </div>
      )}

      {active && pending.length > 0 && (
        <div className="people">
          <h3>Waiting for your answer</h3>
          {pending.map((r) => (
            <div key={r.id} className="request-row">
              <span>
                {r.requester.display_name} · {plural(r.seats, "seat")}
              </span>
              <span className="actions">
                <button className="primary small" onClick={() => act(() => api.acceptRequest(r.id))}>
                  Accept
                </button>
                <button className="small" onClick={() => act(() => api.declineRequest(r.id))}>
                  Decline
                </button>
              </span>
            </div>
          ))}
        </div>
      )}

      {active && requests.length === 0 && <p className="muted">No requests yet.</p>}
      {error && <p className="error">{error}</p>}
      {active && (
        <div className="actions">
          <ShareButton tripId={trip.id} />
          {hasStarted(trip) && (
            <button className="primary small" onClick={() => act(() => api.completeTrip(trip.id))}>
              Mark completed
            </button>
          )}
          <button
            className="danger small"
            onClick={() => window.confirm("Cancel this ride?") && act(() => api.cancelTrip(trip.id))}
          >
            Cancel ride
          </button>
        </div>
      )}
    </article>
  );
}

function JoinedTrip({ req, onChange }) {
  const { trip } = req;
  const [error, setError] = useState("");
  const canCancel = ["pending", "accepted"].includes(req.status) && isActive(trip);
  const share = splitFare(trip, 0);

  async function cancel() {
    if (!window.confirm("Cancel your request?")) return;
    try {
      await api.cancelRequest(req.id);
      onChange();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <article className="card trip">
      <div className="trip-head">
        <strong>{formatTime(trip.depart_at)}</strong>
        <StatusPill status={trip.status === "cancelled" ? "cancelled" : req.status} />
      </div>
      <p className="route">
        {trip.start.label} → {trip.end.label}
      </p>
      <p className="muted">
        Host: {trip.host.display_name} · {VEHICLE_LABEL[trip.vehicle]}
      </p>
      {trip.status === "cancelled" && <p className="error">The host cancelled this ride.</p>}
      {req.status === "pending" && isActive(trip) && (
        <p className="muted">Waiting for {trip.host.display_name} to accept.</p>
      )}
      {req.host_contact && trip.status === "completed" && (
        <div className="people">
          <RatePerson tripId={trip.id} person={req.host_contact} />
        </div>
      )}
      {req.host_contact && trip.status !== "completed" && (
        <div className="people">
          <h3>Your host</h3>
          <Contact person={req.host_contact} />
          {share && req.status === "accepted" && <p className="fare">Your share: about ₹{share}</p>}
          <SafetyActions userId={req.host_contact.id} tripId={trip.id} />
          {isActive(trip) && <ShareButton tripId={trip.id} />}
        </div>
      )}
      {error && <p className="error">{error}</p>}
      {canCancel && (
        <button className="danger small" onClick={cancel}>
          Cancel request
        </button>
      )}
    </article>
  );
}

export default function MyRides() {
  const [hosted, setHosted] = useState(null);
  const [joined, setJoined] = useState(null);
  const [next, setNext] = useState({ hosted: null, joined: null }); // cursors for "Show older"
  const [version, setVersion] = useState(0);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [trips, requests] = await Promise.all([api.myTrips(), api.myRequests()]);
      setHosted(trips.items);
      setJoined(requests.items);
      setNext({ hosted: trips.next_cursor, joined: requests.next_cursor });
      setVersion((v) => v + 1);
      setError("");
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);
  useLiveEvents(load); // someone requested, accepted, cancelled… show it without Refresh

  async function showOlder(kind) {
    try {
      if (kind === "hosted") {
        const more = await api.myTrips(next.hosted);
        setHosted((all) => [...all, ...more.items]);
        setNext((n) => ({ ...n, hosted: more.next_cursor }));
      } else {
        const more = await api.myRequests(next.joined);
        setJoined((all) => [...all, ...more.items]);
        setNext((n) => ({ ...n, joined: more.next_cursor }));
      }
    } catch (err) {
      setError(err.message);
    }
  }

  if (error) return <p className="error card">{error}</p>;
  if (!hosted || !joined) return <p className="muted center">Loading…</p>;

  return (
    <>
      <NotificationPrompt />
      <div className="section-head">
        <h2>Rides I'm hosting</h2>
        <button className="small" onClick={load}>Refresh</button>
      </div>
      {hosted.length === 0 && <p className="muted card">You haven't offered any rides yet.</p>}
      {hosted.map((trip) => (
        <HostedTrip key={trip.id} trip={trip} version={version} onChange={load} />
      ))}
      {next.hosted && (
        <button className="more" onClick={() => showOlder("hosted")}>
          Show older rides
        </button>
      )}

      <h2>Rides I asked to join</h2>
      {joined.length === 0 && <p className="muted card">No requests yet. Find a ride to join one.</p>}
      {joined.map((req) => (
        <JoinedTrip key={req.id} req={req} onChange={load} />
      ))}
      {next.joined && (
        <button className="more" onClick={() => showOlder("joined")}>
          Show older requests
        </button>
      )}
    </>
  );
}
