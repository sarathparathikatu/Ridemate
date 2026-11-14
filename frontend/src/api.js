// Every HTTP call lives here, so pages never deal with URLs, headers or tokens.
const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "ridemate_token";

// localStorage keeps you logged in across reloads. Trade-off: any script running on the
// page can read it (XSS risk); an httpOnly cookie avoids that but needs CSRF protection.
let memoryToken = null; // fallback if the browser blocks storage

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY) ?? memoryToken;
  } catch {
    return memoryToken;
  }
}

export function setToken(token) {
  memoryToken = token;
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // storage blocked: the in-memory copy keeps this tab logged in
  }
}

function describe(detail) {
  // FastAPI sends 422 validation errors as a list, everything else as a string.
  if (Array.isArray(detail)) return detail.map((d) => d.msg.replace(/^Value error, /, "")).join("; ");
  return detail ?? "Something went wrong";
}

async function request(path, { method = "GET", json, form } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`; // the JWT travels on every call

  let body;
  if (json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(json);
  } else if (form) {
    body = new URLSearchParams(form); // login uses OAuth2's form format, not JSON
  }

  let res;
  try {
    res = await fetch(`${API_URL}${path}`, { method, headers, body });
  } catch {
    throw new ApiError(0, "Can't reach the RideMate server. Is the backend running?");
  }

  if (res.status === 401 && token) {
    // Token expired or invalid: forget it and let the app show the login screen.
    setToken(null);
    window.dispatchEvent(new Event("ridemate:logout"));
  }
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(res.status, describe(data.detail));
  }
  return res.json();
}

const post = (path, json) => request(path, { method: "POST", json });

export const api = {
  register: (data) => post("/auth/register", data),
  login: (email, password) =>
    request("/auth/login", { method: "POST", form: { username: email, password } }),
  me: () => request("/users/me"),
  places: () => request("/places"),
  searchTrips: (params) => request(`/trips/search?${new URLSearchParams(params)}`),
  postTrip: (data) => post("/trips", data),
  myTrips: () => request("/trips/mine"),
  cancelTrip: (id) => post(`/trips/${id}/cancel`),
  requestToJoin: (id, seats) => post(`/trips/${id}/requests`, { seats }),
  tripRequests: (id) => request(`/trips/${id}/requests`),
  myRequests: () => request("/requests/mine"),
  acceptRequest: (id) => post(`/requests/${id}/accept`),
  declineRequest: (id) => post(`/requests/${id}/decline`),
  cancelRequest: (id) => post(`/requests/${id}/cancel`),
};
