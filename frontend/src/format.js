export const VEHICLE_LABEL = { auto: "Auto", cab: "Cab", any: "Auto or cab" };
export const MAX_SEATS = { auto: 2, cab: 3, any: 2 }; // co-travellers besides the host

// The API speaks UTC; the browser shows the user's local time (IST).
export function formatTime(iso) {
  return new Date(iso).toLocaleString("en-IN", {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
  });
}

// <input type="datetime-local"> works in local "YYYY-MM-DDTHH:mm" with no timezone.
export function toLocalInput(date) {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

// ...and back to a full UTC timestamp ("...Z") for the API, which rejects naive times.
export const fromLocalInput = (value) => new Date(value).toISOString();

export const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

// Estimated share if `extraSeats` more people join: host + current riders + newcomers.
export function splitFare(trip, extraSeats = 1) {
  if (!trip.fare_estimate) return null;
  return Math.ceil(trip.fare_estimate / (1 + trip.seats_taken + extraSeats));
}
