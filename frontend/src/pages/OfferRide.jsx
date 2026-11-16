import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { VehicleArt } from "../components/Art.jsx";
import Icon from "../components/Icon.jsx";
import { PlaceChips, PlaceSearch, RouteFields, useRoutePicker } from "../components/LocationPicker.jsx";
import MapShell from "../components/MapShell.jsx";
import RideMap from "../components/RideMap.jsx";
import { MAX_SEATS, VEHICLE_LABEL, fromLocalInput, toLocalInput } from "../format.js";
import { usePlaces } from "../usePlaces.js";
import { describeRoute, useRoadRoute } from "../useRoadRoute.js";

const asPoint = ({ lat, lng, label }) => ({ lat, lng, label: label.trim() || "Pinned spot" });
const FLEX_OPTIONS = [0, 10, 15, 30];
const VEHICLE_HINT = { auto: "Up to 2 riders", cab: "Up to 3 riders", any: "Whichever comes" };

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
  const picker = useRoutePicker({ places, from, to, onFrom: setFrom, onTo: setTo });
  const road = useRoadRoute(from, to);

  const maxSeats = MAX_SEATS[vehicle];
  // If every seat fills: the host plus `seats` riders share the fare.
  const perPerson = fare ? Math.ceil(Number(fare) / (1 + seats)) : null;

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
    <MapShell
      map={
        <RideMap
          fill
          suggestions={places}
          from={from}
          to={to}
          road={road?.points}
          onTap={picker.tap}
          onPickPlace={picker.pickPlace}
        />
      }
    >
      <div>
        <p className="eyebrow">You book. They share.</p>
        <h1 className="sheet-title">Offer a ride</h1>
      </div>
      <form className="form" onSubmit={submit}>
        <RouteFields picker={picker} from={from} to={to} onFrom={setFrom} onTo={setTo} editableLabels />
        {road && (
          <p className="route-facts">
            <Icon name="rides" size={16} />
            {describeRoute(road)}
          </p>
        )}
        <PlaceSearch picker={picker} near={from ?? to} />
        <PlaceChips places={places} picker={picker} />

        <div className="field">
          <span className="field-label">Vehicle</span>
          <div className="vehicles" role="radiogroup" aria-label="Vehicle">
            {Object.entries(VEHICLE_LABEL).map(([value, text]) => (
              <button
                key={value}
                type="button"
                role="radio"
                aria-checked={vehicle === value}
                className={vehicle === value ? "vehicle on" : "vehicle"}
                onClick={() => changeVehicle(value)}
              >
                <VehicleArt vehicle={value} width={64} />
                <strong>{text}</strong>
                <span>{VEHICLE_HINT[value]}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="stepper-row">
          <div>
            <strong>Seats for others</strong>
            <p className="muted small-text">
              Up to {maxSeats} in {vehicle === "cab" ? "a cab" : "an auto"}
            </p>
          </div>
          <div className="stepper" role="group" aria-label="Seats for others">
            <button
              type="button"
              className="round-button"
              onClick={() => setSeats((s) => Math.max(1, s - 1))}
              disabled={seats <= 1}
              aria-label="One seat fewer"
            >
              <Icon name="minus" />
            </button>
            <span className="stepper-value" aria-live="polite">
              {seats}
            </span>
            <button
              type="button"
              className="round-button"
              onClick={() => setSeats((s) => Math.min(maxSeats, s + 1))}
              disabled={seats >= maxSeats}
              aria-label="One seat more"
            >
              <Icon name="plus" />
            </button>
          </div>
        </div>

        <label>
          <span className="field-label">Leaving at</span>
          <input type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} required />
        </label>
        <div className="field">
          <span className="field-label">I can wait</span>
          <div className="chips">
            {FLEX_OPTIONS.map((m) => (
              <button
                key={m}
                type="button"
                className={flex === m ? "chip on" : "chip"}
                aria-pressed={flex === m}
                onClick={() => setFlex(m)}
              >
                {m === 0 ? "No waiting" : `±${m} min`}
              </button>
            ))}
          </div>
        </div>

        <label>
          <span className="field-label">
            Expected fare <span className="muted-inline">(optional)</span>
          </span>
          <span className="input-prefix">
            <span>₹</span>
            <input
              type="number"
              min="0"
              max="5000"
              value={fare}
              onChange={(e) => setFare(e.target.value)}
              placeholder="e.g. 150"
              aria-label="Expected fare in rupees"
            />
          </span>
        </label>
        {perPerson != null && (
          <div className="split-card">
            <div>
              <span className="split-card-label">If all {seats + 1} of you share, each pays about</span>
              <strong>₹{perPerson}</strong>
            </div>
            <span className="split-card-save">Save up to ₹{Number(fare) - perPerson}</span>
          </div>
        )}
        <label>
          <span className="field-label">
            Note <span className="muted-inline">(optional)</span>
          </span>
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            maxLength={200}
            placeholder="e.g. Blue shirt, waiting at the main exit"
          />
        </label>

        {(placesError || error) && <p className="error">{placesError || error}</p>}
        <div className="sheet-cta">
          <button className="cta" disabled={busy}>
            {busy ? "Posting…" : "Post ride"}
          </button>
        </div>
        <p className="muted small-text center lock-line">
          <Icon name="lock" size={14} /> Your phone and email are shared only with riders you accept.
        </p>
      </form>
    </MapShell>
  );
}
