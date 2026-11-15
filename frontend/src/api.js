// Every HTTP call lives here, so pages never deal with URLs, headers or tokens.
export const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const ACCESS_KEY = "ridemate_token";
const REFRESH_KEY = "ridemate_refresh";

// localStorage keeps you logged in across reloads. Trade-off: any script running on the
// page can read it (XSS risk); an httpOnly cookie avoids that but needs CSRF protection.
const memory = {}; // fallback if the browser blocks storage

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

function read(key) {
  try {
    return localStorage.getItem(key) ?? memory[key] ?? null;
  } catch {
    return memory[key] ?? null;
  }
}

function write(key, value) {
  memory[key] = value;
  try {
    if (value) localStorage.setItem(key, value);
    else localStorage.removeItem(key);
  } catch {
    // storage blocked: the in-memory copy keeps this tab logged in
  }
}

export const getToken = () => read(ACCESS_KEY);
const getRefreshToken = () => read(REFRESH_KEY);

export function setTokens(tokens) {
  write(ACCESS_KEY, tokens?.access_token ?? null);
  write(REFRESH_KEY, tokens?.refresh_token ?? null);
}

// Only one refresh at a time: if five requests hit a 401 together, they all wait on
// this same promise instead of spending the refresh token five times.
let refreshing = null;

export function refreshTokens() {
  refreshing ??= (async () => {
    const used = getRefreshToken();
    if (!used) return false;
    const res = await fetch(`${API_URL}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: used }),
    }).catch(() => null);
    if (res?.ok) {
      setTokens(await res.json());
      return true;
    }
    // Another tab may have refreshed first and saved a newer pair: use that one.
    return getRefreshToken() !== used && Boolean(getToken());
  })().finally(() => {
    refreshing = null;
  });
  return refreshing;
}

function describe(detail) {
  // FastAPI sends 422 validation errors as a list, everything else as a string.
  if (Array.isArray(detail)) return detail.map((d) => d.msg.replace(/^Value error, /, "")).join("; ");
  return detail ?? "Something went wrong";
}

async function request(path, options = {}, canRetry = true) {
  const { method = "GET", json, form } = options;
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

  if (res.status === 401 && token && !path.startsWith("/auth/")) {
    // Access token expired: quietly get a new one and repeat the request once.
    if (canRetry && (await refreshTokens())) return request(path, options, false);
    // Refresh failed too (expired, revoked, or stolen-and-burned): back to login.
    setTokens(null);
    window.dispatchEvent(new Event("ridemate:logout"));
  }
  if (res.status === 204) return null;
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(res.status, describe(data.detail));
  }
  return res.json();
}

const post = (path, json) => request(path, { method: "POST", json });

// "?a=1&b=2", skipping empty values (e.g. no cursor on the first page).
function query(params) {
  const clean = Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "");
  return clean.length ? `?${new URLSearchParams(clean)}` : "";
}

export const api = {
  register: (data) => post("/auth/register", data),
  login: (email, password) =>
    request("/auth/login", { method: "POST", form: { username: email, password } }),
  logout: () => post("/auth/logout", { refresh_token: getRefreshToken() ?? "" }),
  me: () => request("/users/me"),
  places: () => request("/places"),
  // Lists come back as pages: { items, next_cursor }. Pass next_cursor back for more.
  searchTrips: (params) => request(`/trips/search${query(params)}`),
  postTrip: (data) => post("/trips", data),
  myTrips: (cursor) => request(`/trips/mine${query({ cursor })}`),
  cancelTrip: (id) => post(`/trips/${id}/cancel`),
  requestToJoin: (id, seats) => post(`/trips/${id}/requests`, { seats }),
  tripRequests: (id) => request(`/trips/${id}/requests`),
  myRequests: (cursor) => request(`/requests/mine${query({ cursor })}`),
  acceptRequest: (id) => post(`/requests/${id}/accept`),
  declineRequest: (id) => post(`/requests/${id}/decline`),
  cancelRequest: (id) => post(`/requests/${id}/cancel`),
  // Trust & safety
  sendPhoneCode: (phone) => post("/users/me/phone/send-code", { phone }),
  verifyPhone: (code) => post("/users/me/phone/verify", { code }),
  completeTrip: (id) => post(`/trips/${id}/complete`),
  rate: (tripId, rating) => post(`/trips/${tripId}/ratings`, rating),
  shareTrip: (id) => post(`/trips/${id}/share`),
  viewShare: (token) => request(`/share/${encodeURIComponent(token)}`),
  block: (userId) => post(`/users/${userId}/block`),
  unblock: (userId) => request(`/users/${userId}/block`, { method: "DELETE" }),
  blocked: () => request("/users/me/blocks"),
  report: (userId, report) => post(`/users/${userId}/report`, report),
};
