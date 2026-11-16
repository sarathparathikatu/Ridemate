import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api.js";
import { VehicleArt } from "../components/Art.jsx";
import Icon from "../components/Icon.jsx";
import RideMap from "../components/RideMap.jsx";
import { Notice, RouteLine, SkeletonCards, StatusPill } from "../components/ui.jsx";
import { VEHICLE_LABEL, formatClock, formatDay } from "../format.js";

// Public page (no login): what a family member sees when you share a ride with them.
export default function SharedRide() {
  const { token } = useParams();
  const [ride, setRide] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.viewShare(token).then(setRide).catch((err) => setError(err.message));
  }, [token]);

  if (error) {
    return (
      <div className="page narrow">
        <Notice kind="error">{error}</Notice>
      </div>
    );
  }
  if (!ride) {
    return (
      <div className="page narrow">
        <SkeletonCards count={1} />
      </div>
    );
  }

  return (
    <div className="page narrow">
      <header className="page-head">
        <div>
          <p className="eyebrow">Shared with you</p>
          <h1>{ride.shared_by}'s ride</h1>
        </div>
        <StatusPill status={ride.status} />
      </header>
      <article className="trip-card">
        <RideMap from={ride.start} to={ride.end} />
        <div className="trip-body">
          <div className="trip-when">
            <div className="ride-when">
              <span className="ride-time">{formatClock(ride.depart_at)}</span>
              <span className="ride-day">
                {formatDay(ride.depart_at)} · {VEHICLE_LABEL[ride.vehicle]}
              </span>
            </div>
            <VehicleArt vehicle={ride.vehicle} width={64} />
          </div>
          <RouteLine from={ride.start.label} to={ride.end.label} />
          <div className="meta">
            <span>
              <Icon name="user" size={16} />
              Host: {ride.host_name}
            </span>
            <span>
              <Icon name="users" size={16} />
              {ride.riders} in this ride
            </span>
          </div>
          <p className="hint">
            <Icon name="lock" size={16} />
            <span>Only the route and time are shown here. Phone numbers stay private.</span>
          </p>
        </div>
      </article>
    </div>
  );
}
