import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { RouteArt, VehicleArt } from "../components/Art.jsx";
import Contact from "../components/Contact.jsx";
import Icon from "../components/Icon.jsx";
import { RatePerson, SafetyActions, ShareButton, TrustBadges } from "../components/Trust.jsx";
import { Avatar, EmptyState, Notice, RouteLine, SkeletonCards, StatusPill, Timeline } from "../components/ui.jsx";
import { VEHICLE_LABEL, formatClock, formatDay, plural, splitFare } from "../format.js";
import { NotificationPrompt, useLiveEvents } from "../live.jsx";

const isActive = (trip) => trip.status === "open" || trip.status === "full";
// The host can close the ride from 30 minutes before departure (the API enforces it too).
const hasStarted = (trip) => new Date(trip.depart_at) <= new Date(Date.now() + 30 * 60000);

// The top of every ride card: route artwork, status, time and vehicle.
function TripHeader({ trip, status }) {
  return (
    <>
      <div className="trip-art">
        <RouteArt seed={trip.id} />
        <StatusPill status={status} />
      </div>
      <div className="trip-when">
        <div className="ride-when">
          <span className="ride-time">{formatClock(trip.depart_at)}</span>
          <span className="ride-day">
            {formatDay(trip.depart_at)} · {VEHICLE_LABEL[trip.vehicle]}
          </span>
        </div>
        <VehicleArt vehicle={trip.vehicle} width={64} />
      </div>
      <RouteLine from={trip.start.label} to={trip.end.label} />
    </>
  );
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
    <article className={`trip-card ${active || completed ? "" : "inactive"}`}>
      <div className="trip-body">
        <TripHeader trip={trip} status={trip.status} />

        <div className="seat-meter">
          <div className="seat-dots" aria-hidden="true">
            {Array.from({ length: trip.seats_total }, (_, i) => (
              <span key={i} className={i < trip.seats_taken ? "seat taken" : "seat"}>
                <Icon name="user" size={16} />
              </span>
            ))}
          </div>
          <span className="muted small-text">
            {trip.seats_taken} of {trip.seats_total} seats taken
          </span>
        </div>

        {active && pending.length > 0 && (
          <div className="people">
            <h3 className="people-title">
              <span className="count-badge">{pending.length}</span> Waiting for your answer
            </h3>
            {pending.map((r) => (
              <div key={r.id} className="request-row">
                <div className="person-row">
                  <Avatar name={r.requester.display_name} />
                  <div className="person-text">
                    <strong>{r.requester.display_name}</strong>
                    <span className="muted small-text">wants {plural(r.seats, "seat")}</span>
                    <TrustBadges person={r.requester} />
                  </div>
                </div>
                <div className="actions">
                  <button className="primary small" onClick={() => act(() => api.acceptRequest(r.id))}>
                    Accept
                  </button>
                  <button className="small" onClick={() => act(() => api.declineRequest(r.id))}>
                    Decline
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {accepted.length > 0 && (
          <div className="people">
            <h3 className="people-title">{completed ? "Rate your co-travellers" : "Riding with you"}</h3>
            {accepted.map((r) =>
              completed ? (
                <RatePerson key={r.id} tripId={trip.id} person={r.requester_contact} />
              ) : (
                <div key={r.id} className="person-block">
                  <Contact person={r.requester_contact} extra={plural(r.seats, "seat")} />
                  <SafetyActions userId={r.requester_contact.id} tripId={trip.id} />
                </div>
              ),
            )}
          </div>
        )}

        {active && requests.length === 0 && (
          <p className="waiting">
            <span className="pulse" />
            Looking for co-travellers. You'll get a live alert when someone asks to join.
          </p>
        )}
        {error && <p className="error">{error}</p>}
        {active && (
          <div className="card-actions">
            <ShareButton tripId={trip.id} />
            {hasStarted(trip) && (
              <button className="primary small" onClick={() => act(() => api.completeTrip(trip.id))}>
                <Icon name="check" size={16} />
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
      </div>
    </article>
  );
}

function JoinedTrip({ req, onChange }) {
  const { trip } = req;
  const [error, setError] = useState("");
  const canCancel = ["pending", "accepted"].includes(req.status) && isActive(trip);
  const share = splitFare(trip, 0);
  const done = trip.status === "completed" && req.status === "accepted";
  const status = trip.status === "cancelled" ? "cancelled" : done ? "completed" : req.status;
  // Requested → Accepted → Ride done. Only shown while the request is still alive.
  const step = done ? 2 : req.status === "accepted" ? 1 : 0;
  const showTimeline = trip.status !== "cancelled" && ["pending", "accepted"].includes(req.status);

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
    <article className={`trip-card ${showTimeline ? "" : "inactive"}`}>
      <div className="trip-body">
        <TripHeader trip={trip} status={status} />
        {showTimeline && <Timeline step={step} />}

        {trip.status === "cancelled" && <Notice kind="error">The host cancelled this ride.</Notice>}
        {req.status === "declined" && trip.status !== "cancelled" && (
          <Notice kind="info">This ride didn't work out. Try searching again.</Notice>
        )}
        {req.status === "pending" && isActive(trip) && (
          <p className="waiting">
            <span className="pulse" />
            Waiting for {trip.host.display_name} to accept. Contacts unlock after that.
          </p>
        )}

        {req.host_contact && trip.status === "completed" && (
          <div className="people">
            <RatePerson tripId={trip.id} person={req.host_contact} />
          </div>
        )}
        {req.host_contact && trip.status !== "completed" && (
          <div className="people">
            <h3 className="people-title">Your host</h3>
            <Contact person={req.host_contact} />
            {share && req.status === "accepted" && (
              <div className="split-card">
                <div>
                  <span className="split-card-label">Your share, about</span>
                  <strong>₹{share}</strong>
                </div>
                <span className="split-card-save">Pay the driver directly</span>
              </div>
            )}
            <SafetyActions userId={req.host_contact.id} tripId={trip.id} />
          </div>
        )}
        {!req.host_contact && (
          <p className="muted small-text host-hidden">
            <Icon name="lock" size={14} /> Host: {trip.host.display_name}. Phone and email stay hidden until you're
            accepted.
          </p>
        )}
        {error && <p className="error">{error}</p>}
        {(canCancel || (req.host_contact && isActive(trip))) && (
          <div className="card-actions">
            {req.host_contact && isActive(trip) && <ShareButton tripId={trip.id} />}
            {canCancel && (
              <button className="danger small" onClick={cancel}>
                Cancel request
              </button>
            )}
          </div>
        )}
      </div>
    </article>
  );
}

export default function MyRides() {
  const [hosted, setHosted] = useState(null);
  const [joined, setJoined] = useState(null);
  const [next, setNext] = useState({ hosted: null, joined: null }); // cursors for "Show older"
  const [version, setVersion] = useState(0);
  const [tab, setTab] = useState(null); // phones show one list at a time; laptops show both
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [trips, requests] = await Promise.all([api.myTrips(), api.myRequests()]);
      setHosted(trips.items);
      setJoined(requests.items);
      setNext({ hosted: trips.next_cursor, joined: requests.next_cursor });
      setVersion((v) => v + 1);
      setError("");
      // First load: open the tab that has something in it.
      setTab((current) => current ?? (trips.items.length === 0 && requests.items.length > 0 ? "joined" : "hosted"));
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

  const head = (
    <header className="page-head">
      <h1>Activity</h1>
      <button className="round-button" onClick={load} aria-label="Refresh" title="Refresh">
        <Icon name="refresh" />
      </button>
    </header>
  );

  if (error) {
    return (
      <div className="page">
        {head}
        <Notice kind="error">{error}</Notice>
      </div>
    );
  }
  if (!hosted || !joined) {
    return (
      <div className="page">
        {head}
        <SkeletonCards count={2} />
      </div>
    );
  }

  const activeHosted = hosted.filter(isActive).length;
  const activeJoined = joined.filter((r) => isActive(r.trip) && ["pending", "accepted"].includes(r.status)).length;

  return (
    <div className="page">
      {head}
      <NotificationPrompt />

      <div className="tabs" role="tablist" aria-label="Ride lists">
        <button role="tab" aria-selected={tab === "hosted"} className={tab === "hosted" ? "on" : ""} onClick={() => setTab("hosted")}>
          Hosting {activeHosted > 0 && <span className="count-badge">{activeHosted}</span>}
        </button>
        <button role="tab" aria-selected={tab === "joined"} className={tab === "joined" ? "on" : ""} onClick={() => setTab("joined")}>
          Joining {activeJoined > 0 && <span className="count-badge">{activeJoined}</span>}
        </button>
      </div>

      <div className="columns">
        <section className={`column ${tab === "hosted" ? "shown" : ""}`}>
          <h2 className="column-title">Rides you're hosting</h2>
          {hosted.length === 0 && (
            <EmptyState
              art={<VehicleArt vehicle="auto" width={110} />}
              title="No rides hosted yet"
              text="Booking an auto anyway? Offer the empty seats and split the fare."
            >
              <Link className="button primary" to="/offer">
                Offer a ride
              </Link>
            </EmptyState>
          )}
          {hosted.map((trip) => (
            <HostedTrip key={trip.id} trip={trip} version={version} onChange={load} />
          ))}
          {next.hosted && (
            <button className="more" onClick={() => showOlder("hosted")}>
              Show older rides
            </button>
          )}
        </section>

        <section className={`column ${tab === "joined" ? "shown" : ""}`}>
          <h2 className="column-title">Rides you asked to join</h2>
          {joined.length === 0 && (
            <EmptyState
              art={<VehicleArt vehicle="cab" width={110} />}
              title="No requests yet"
              text="Find someone from your train going your way."
            >
              <Link className="button primary" to="/">
                Find a ride
              </Link>
            </EmptyState>
          )}
          {joined.map((req) => (
            <JoinedTrip key={req.id} req={req} onChange={load} />
          ))}
          {next.joined && (
            <button className="more" onClick={() => showOlder("joined")}>
              Show older requests
            </button>
          )}
        </section>
      </div>
    </div>
  );
}
