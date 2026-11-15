import { useEffect, useState } from "react";
import { api } from "./api.js";

// Known places (stations, landmarks): shown as quick picks on the map and in lists.
export function usePlaces() {
  const [places, setPlaces] = useState([]);
  const [error, setError] = useState("");
  useEffect(() => {
    api.places().then(setPlaces).catch((err) => setError(err.message));
  }, []);
  return { places, error };
}
