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

// "5:39 pm" — the big number on a ride card.
export function formatClock(iso) {
  return new Date(iso).toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" });
}

// "Today", "Tomorrow" or "Sun, 15 Nov" — the small line under the time.
export function formatDay(iso) {
  const date = new Date(iso);
  const startOf = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const days = Math.round((startOf(date) - startOf(new Date())) / 86400000);
  if (days === 0) return "Today";
  if (days === 1) return "Tomorrow";
  if (days === -1) return "Yesterday";
  return date.toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" });
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
