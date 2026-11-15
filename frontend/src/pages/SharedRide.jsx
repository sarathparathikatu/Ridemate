import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api.js";
import RideMap from "../components/RideMap.jsx";
import { VEHICLE_LABEL, formatTime } from "../format.js";

// Public page (no login): what a family member sees when you share a ride with them.
export default function SharedRide() {
  const { token } = useParams();
  const [ride, setRide] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.viewShare(token).then(setRide).catch((err) => setError(err.message));
  }, [token]);

  if (error) return <p className="card error">{error}</p>;
  if (!ride) return <p className="muted center">Loading…</p>;

  return (
    <article className="card trip">
      <p className="muted">{ride.shared_by} shared this ride with you</p>
      <div className="trip-head">
        <strong>{formatTime(ride.depart_at)}</strong>
        <span className={`pill ${ride.status}`}>{ride.status}</span>
      </div>
      <p className="route">
        {ride.start.label} → {ride.end.label}
      </p>
      <p className="muted">
        Host: {ride.host_name} · {VEHICLE_LABEL[ride.vehicle]} · {ride.riders} people in this ride
      </p>
      <RideMap from={ride.start} to={ride.end} />
      <p className="muted">Only the route and time are shown here. Phone numbers stay private.</p>
    </article>
  );
}
