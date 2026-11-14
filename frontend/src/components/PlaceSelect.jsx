import { useEffect, useState } from "react";
import { api } from "../api.js";

export const DEFAULT_STATION = "Kazhakoottam Railway Station";

export function usePlaces() {
  const [places, setPlaces] = useState([]);
  const [error, setError] = useState("");
  useEffect(() => {
    api.places().then(setPlaces).catch((err) => setError(err.message));
  }, []);
  return { places, error };
}

export function PlaceSelect({ label, places, value, onChange, exclude }) {
  const groups = [
    ["Stations", places.filter((p) => p.kind === "station")],
    ["Areas", places.filter((p) => p.kind === "area")],
  ];
  return (
    <label>
      {label}
      <select value={value} onChange={(e) => onChange(e.target.value)} required>
        <option value="">Choose…</option>
        {groups.map(([name, items]) => (
          <optgroup key={name} label={name}>
            {items
              .filter((p) => String(p.id) !== String(exclude))
              .map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
          </optgroup>
        ))}
      </select>
    </label>
  );
}
