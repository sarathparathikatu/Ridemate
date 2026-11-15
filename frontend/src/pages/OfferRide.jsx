import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api } from "../api.js";
import LocationPicker from "../components/LocationPicker.jsx";
import { usePlaces } from "../usePlaces.js";
import { MAX_SEATS, VEHICLE_LABEL, fromLocalInput, toLocalInput } from "../format.js";

const asPoint = ({ lat, lng, label }) => ({ lat, lng, label: label.trim() || "Pinned spot" });

export default function OfferRide() {
  const navigate = useNavigate();
  const prefill = useLocation().state ?? {}; // set when coming from an empty search
  const { places, error: placesError } = usePlaces();
  const [from, setFrom] = useState(prefill.from ?? null);
  const [to, setTo] = useState(prefill.to ?? null);
  const [when, setWhen] = useState(prefill.when ?? toLocalInput(new Date(Date.now() + 15 * 60000)));
  const [vehicle, setVehicle] = useState("auto");
  const [seats, setSeats] = useState(2);
  const [flex, setFlex] = useState(15);
  const [fare, setFare] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const maxSeats = MAX_SEATS[vehicle];

  function changeVehicle(value) {
    setVehicle(value);
    setSeats((s) => Math.min(s, MAX_SEATS[value]));
  }

  async function submit(event) {
    event.preventDefault();
    if (!from || !to) {
      setError("Set your pickup and destination (use your location, or tap the map).");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api.postTrip({
        start: asPoint(from),
        end: asPoint(to),
        depart_at: fromLocalInput(when),
        vehicle,
        seats_total: seats,
        flex_minutes: flex,
        fare_estimate: fare === "" ? null : Number(fare),
        note: note.trim() || null,
      });
      navigate("/rides");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="card form" onSubmit={submit}>
      <h1>Offer a ride</h1>
      <p className="muted">You book the auto or cab; others from your train join and split the fare.</p>
      <LocationPicker places={places} from={from} to={to} onFrom={setFrom} onTo={setTo} editableLabels />
      <label>
        Leaving at
        <input type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} required />
      </label>
      <div className="row">
        <label>
          Vehicle
          <select value={vehicle} onChange={(e) => changeVehicle(e.target.value)}>
            {Object.entries(VEHICLE_LABEL).map(([value, text]) => (
              <option key={value} value={value}>{text}</option>
            ))}
          </select>
        </label>
        <label>
          Seats for others
          <select value={seats} onChange={(e) => setSeats(Number(e.target.value))}>
            {Array.from({ length: maxSeats }, (_, i) => i + 1).map((n) => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
        </label>
      </div>
      <div className="row">
        <label>
          I can wait
          <select value={flex} onChange={(e) => setFlex(Number(e.target.value))}>
            {[0, 10, 15, 30].map((m) => (
              <option key={m} value={m}>±{m} min</option>
            ))}
          </select>
        </label>
        <label>
          Expected fare (₹)
          <input type="number" min="0" max="5000" value={fare} onChange={(e) => setFare(e.target.value)} placeholder="optional" />
        </label>
      </div>
      <label>
        Note <span className="muted">(optional)</span>
        <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={200} placeholder="e.g. Blue shirt, waiting at the main exit" />
      </label>
      {(placesError || error) && <p className="error">{placesError || error}</p>}
      <button className="primary" disabled={busy}>
        {busy ? "Posting…" : "Post ride"}
      </button>
    </form>
  );
}
