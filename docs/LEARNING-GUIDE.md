# RideMate learning guide

Everything RideMate uses, explained in plain words: what it is, why it's there, where it
lives in the code, and the interview questions it prepares you for. Read it with the code
open next to it. Paths are relative to the repository root.

How to use this guide:
1. Read a section.
2. Open the files it names and find the lines it describes.
3. Answer its interview questions out loud, without looking.

---

## Part 1 — Foundations

### 1.1 How a request flows through the backend

```
Phone (React)  ──HTTP──►  router  ──►  dependencies  ──►  service  ──►  MySQL
                         (URLs)     (who are you?      (the rules)    (data)
                                     DB session)
               ◄──JSON──  schema filters the response (what this caller may see)
```

| Layer | Folder | Job |
|---|---|---|
| Routers | `backend/app/routers/` | Map URLs to functions. Thin: no business rules. |
| Dependencies | `backend/app/dependencies/` | Reusable steps FastAPI runs first: the logged-in user, a DB session, rate limits. |
| Services | `backend/app/services/` | The rules ("only the host can accept"). Know nothing about HTTP. |
| Models | `backend/app/models/` | Tables, as Python classes (SQLAlchemy ORM). |
| Schemas | `backend/app/schemas/` | What JSON may come in and go out (Pydantic). |

Why split it like this: each layer has one reason to change, services can be tested and
reused (the MCP server reuses the API; the API reuses the services), and a security rule
lives in exactly one place.

**Interview:** *"How do you structure a FastAPI project?"*
Routers for HTTP, a service layer for business logic, schemas for validation, models for
persistence, dependencies for cross-cutting concerns like auth and DB sessions. Services
raise domain errors (`backend/app/services/errors.py`); one exception handler in `main.py`
turns them into HTTP status codes, so endpoints stay free of try/except.

### 1.2 SQLAlchemy and Alembic

- **SQLAlchemy ORM** maps classes to tables: a class is a table, an attribute is a column,
  an object is a row. You write Python; it writes the SQL.
- **Alembic** changes the table *structure* through versioned migration files
  (`backend/migrations/versions/`). Workflow: change a model, then
  `alembic revision --autogenerate -m "..."`, read the file, then `alembic upgrade head`.
- **Autogenerate only sees structure.** It never writes data, and it can't tell a rename
  from drop+add. Read every generated file.

Real examples in this repo where the generated file had to be edited by hand:

| Migration | Hand edit | Why |
|---|---|---|
| `*_ridemate_places_trips_join_requests.py` | 3-step `display_name`; seed places | Adding a NOT NULL column to a table with rows; autogenerate never adds data |
| `*_place_coordinates.py` | 3-step lat/lng with backfill | Same reason |
| `*_trips_search_index.py` | Check-then-drop of the FK's index | MySQL manages that index partly on its own (see 3.2) |

**Interview:** *"How do you add a NOT NULL column to a table with millions of rows?"*
Add it as nullable, backfill it (in batches for a big table), then make it NOT NULL. Never
in one step, and on large MySQL tables consider online schema-change tools.

**Interview:** *"Why is a failed migration more dangerous on MySQL than on PostgreSQL?"*
MySQL commits every DDL statement immediately, so a migration that fails halfway leaves
the schema half-changed. This happened while building RideMate: a `CREATE INDEX` succeeded,
the next statement failed, and Alembic still recorded the old version. The fix was
`alembic stamp` to record the true state. Keep MySQL migrations small.

### 1.3 Authentication: passwords, JWT, refresh tokens

| Piece | File | Key idea |
|---|---|---|
| Password hashing | `backend/app/core/security.py` | bcrypt: slow on purpose, salted, run in a thread (`run_in_threadpool`) so it doesn't block the event loop |
| Access token (JWT) | `security.py` (`create_access_token`, `decode_access_token`) | Signed, not encrypted; 30 minutes; checked without a DB lookup |
| Current user | `backend/app/dependencies/auth.py` | One dependency, reused by every protected endpoint |
| Refresh token | `backend/app/services/token_service.py` | Random string, only its SHA-256 stored, rotated on every use |

**Refresh token rotation and reuse detection.** Each refresh issues a new token and kills
the old one. Tokens from one login share a `family_id`. If an already-used token comes back
(after a 30 s grace period for two tabs racing), it was probably stolen, so the whole
family is revoked and both thief and owner must log in again.

Why SHA-256 for refresh tokens but bcrypt for passwords? Passwords are guessable, so their
hash must be slow. A refresh token is 256 random bits, so nobody can guess it, and a fast
hash lets the server look it up on every refresh.

**Interview:** *"JWTs are stateless. How do you log a user out?"*
Short-lived access tokens (30 min) plus server-side refresh tokens. Logout revokes the
refresh token family (`POST /auth/logout`), so no new access tokens can be issued; the
current one expires within minutes. For instant revocation, keep a denylist in Redis.

**Interview:** *"What's the `alg: none` attack?"*
An attacker sends a token whose header says "no signature". Libraries that trust the header
accept it. RideMate passes `algorithms=["HS256"]` explicitly, so it's rejected.

---

## Part 2 — RideMate's core

### 2.1 Authorization: who may see and do what

- The host of a ride is **always** `current_user.id` from the token, never a field in the
  request body (`trip_service.create_trip`).
- **Two views of the same data**: search results use `PersonOut` (name, badge, rating);
  contact details (`ContactOut`) only appear for people inside an accepted ride
  (`schemas/join_request.py`, `trip_service.get_trip_detail`).

**Interview:** *"What's the difference between authentication and authorization?"*
Authentication is who you are (the token). Authorization is what you may do with a specific
resource ("you are the host of trip 7, so you may cancel it"). Checking only the first is
the classic IDOR bug: changing an id in the URL to reach someone else's data.

### 2.2 The race for the last seat

`backend/app/services/request_service.py` → `accept_request`.

Two accepts for the last seat arriving together would both read "1 seat left" and both
succeed. The fix is `SELECT ... FOR UPDATE` on the trip row: the second transaction waits
until the first commits, then reads 0 seats and gets a 409.

Proof: `backend/tests/test_rides.py::test_last_seat_cannot_be_double_booked`. With the lock
it returns `[200, 409]`; with the lock removed it returned `[200, 200]` (verified while
building).

Deadlock prevention: every function locks the **trip row first, then the request row**, so
two transactions can never wait on each other in a circle.

**Interview:** *"How do you prevent double booking?"*
Pessimistic locking (`SELECT ... FOR UPDATE`, as here), or optimistic: a conditional update
like `UPDATE trips SET seats_taken = seats_taken + 1 WHERE id = ? AND seats_taken < seats_total`
and check the affected-row count. Either way, test it with truly concurrent requests.

### 2.3 Timezones

MySQL stores UTC (`SET time_zone = '+00:00'` on every connection, `backend/app/db/session.py`).
The API accepts only timezone-aware times and returns times labelled UTC
(`backend/app/schemas/common.py`); the browser shows IST. A naive "6:15" is rejected
because you can't know whose 6:15 it was.

---

## Part 3 — Scale (Layer 2)

### 3.1 Cursor (keyset) pagination

`backend/app/schemas/pagination.py`, used by search, my trips and my requests.

Instead of `OFFSET 40 LIMIT 20` ("skip 40 rows"), the client sends a cursor meaning "after
the ride at 06:15 with id 42", and the query asks for `(depart_at, id) > (06:15, 42)`.

| | OFFSET pagination | Keyset (cursor) pagination |
|---|---|---|
| Page 500 | Reads and throws away 10,000 rows | As fast as page 1 (index seek) |
| New rows added while paging | Items skipped or shown twice | Stable |
| Jump to page N | Easy | Not possible (fine for "Load more") |

The server fetches `limit + 1` rows: the extra one only tells it there's a next page.

### 3.2 The search index, proven with EXPLAIN

> History: this section describes the first, place-based search. Search later moved to
> free locations with a SPATIAL index (Part 5), and `scripts/explain_search.py` now
> demonstrates that. The B-tree lessons below still apply.

Index: `ix_trips_search (from_place_id, status, depart_at)` in `backend/app/models/trip.py`.
Rule: **equality columns first, the range column last.** MySQL can then jump straight to
"from = station AND status = open" and read the `depart_at` range already in order.

Measured on 30,000 rides (with the place-based version of the script):

| | Without the index | With it |
|---|---|---|
| Plan | `type=ALL`, full table scan + filesort | `type=range`, covering index scan |
| Rows read | ~30,000 | 37 |
| Time | 19.4 ms | 0.036 ms (~500x faster) |

Things learnt the hard way:
- InnoDB auto-creates an index for every foreign key column, and **silently drops it**
  when you add another index that can serve the FK, but only if it created it implicitly.
- A left-prefix index makes a shorter one redundant (`(a, b, c)` covers queries on `a`),
  and redundant indexes slow every write.

**Interview:** *"How would you speed up a slow query?"*
`EXPLAIN` / `EXPLAIN ANALYZE` it: look for `type=ALL` (full scan), large `rows`, and
`Using filesort`. Add a composite index in the right column order, re-check the plan, and
measure. Don't index everything: each index costs on writes.

### 3.3 Redis and the search cache

`backend/app/core/kv.py` is a tiny store with Redis when `REDIS_URL` is set and process
memory otherwise (fine for one server; that's why production sets Redis).

Search uses **cache-aside** (`trip_service.search_trips`): look in the cache, and on a miss
query MySQL and store the result for 30 s. Invalidation uses **versioned keys**: every
cache key contains a version number, and any change that affects results bumps it
(`invalidate_search`), making all old entries unreachable at once. Positions are snapped
to a ~100 m grid so people standing near each other share entries. (With free locations
the version is global; per-area versions would keep more of the cache warm at scale.) Per-user
filtering (your own rides, blocked users) happens *after* the cache, so one cached page
serves everyone on the train.

**Interview:** *"What's hard about caching?"*
Invalidation and consistency. Options: short TTLs (accept briefly stale data), explicit
deletes (you must know every affected key), or versioned keys (bump one counter). Also
consider stampedes: many requests missing at once and all hitting the database.

### 3.4 Rate limiting

`backend/app/dependencies/rate_limit.py`: a **fixed-window counter**. One counter per
(action, who, minute window), `INCR` plus an expiry, 429 with `Retry-After` when over the
limit. Per IP before login (login, register), per user after (posting, joining, OTP).

Its weakness showed up in the tests: 11 requests that happened to straddle a minute boundary
landed in two windows, and the limit never triggered (a flaky test). The test now freezes
the limiter's clock. Sliding windows or token buckets avoid the boundary burst.

**Interview:** *"Design a rate limiter."*
Fixed window (simple, bursty at boundaries), sliding window log (exact, more memory),
sliding window counter (a good compromise), token bucket (allows controlled bursts). Store
counters in Redis so every server process shares them; key by user or IP; return 429 with
`Retry-After`. Behind a proxy, read the real client IP (`--proxy-headers`).

### 3.5 Where async helps

FastAPI runs on one event loop per process. While one request waits for MySQL or Redis, the
loop serves others, so a full train searching at once doesn't need one thread per person.
Waiting on I/O with `await` is fine. **Slow CPU work blocks everyone**, which is why bcrypt
runs in a thread pool.

**Interview:** *"async def or def in FastAPI?"*
`async def` when everything inside awaits async libraries (aiomysql, redis.asyncio). Plain
`def` endpoints run in a thread pool, fine for blocking libraries. Never call blocking code
inside `async def`.

---

## Part 4 — Real-time and the app shell

### 4.1 WebSockets and pub/sub

| File | Job |
|---|---|
| `backend/app/routers/ws.py` | The `/ws` endpoint; the first message carries the token |
| `backend/app/realtime/connections.py` | Open sockets on *this* process, per user |
| `backend/app/realtime/broker.py` | `publish(user_ids, event)`; with Redis, a pub/sub channel |
| `frontend/src/live.jsx` | Connects, reconnects with backoff, toasts, notifications |

Why the token isn't in the URL: browsers can't add headers to WebSockets, and URLs are
written to server and proxy logs.

Why Redis pub/sub: with several API processes, the host's socket may be on process A while
the rider's request hits process B. B publishes to Redis; every process relays to its own
sockets.

Events are best-effort: they're published after the database commit, and a failed publish
never fails the request (the data is safe; the other side sees it on refresh).

Reconnection uses exponential backoff (1 s, 2 s, 4 s ... 30 s) so a server restart isn't
hammered by every client at once.

**Interview:** *"Polling vs WebSockets vs Server-Sent Events?"*
Polling is simple but wasteful and laggy. SSE is server-to-client only over plain HTTP,
with automatic reconnect. WebSockets are two-way and the lowest latency, but need proxies
configured for the Upgrade handshake and sticky state per connection.

### 4.2 PWA (installable app)

`frontend/public/manifest.webmanifest` (name, icons, colours) and
`frontend/public/sw.js` (service worker). The worker caches only the app shell: pages are
network-first (latest version, cached copy offline) and hashed build files are cache-first.
API data is never cached. It's registered only in production builds, and nginx serves
`sw.js` with `Cache-Control: no-cache` so users never get stuck on an old version.

Not built: Web Push for notifications while the app is fully closed (needs VAPID keys and
a push service). The app notifies while it's open or in a background tab.

### 4.3 React state lessons from this project

- **Refresh didn't show new requests**: each ride card loaded its requests once on mount,
  and React kept the cards mounted. Fix: a `version` counter in the effect's dependencies.
- **Profile showed a stale rating**: it read the user loaded at login. Fix: reload on mount.
- **Silent token refresh**: `frontend/src/api.js` retries a 401 once after refreshing, and
  concurrent 401s share one refresh promise instead of racing.

---

## Part 5 — Maps and location (works in any city)

Rides start and end at **any point**, not only a fixed list of places: the phone's GPS,
a pin dropped on the map, or a known place (grey dots, kept as quick picks). That's what
makes RideMate work in Kozhikode, Thrissur or anywhere, with no setup per city.

### 5.1 How a location is stored

`backend/app/models/trip.py`: each trip has `from_lat/from_lng/from_label` and
`to_lat/to_lng/to_label` (`DECIMAL(9,6)`: exact, ~11 cm precision; FLOAT would round).
`from_place_id/to_place_id` are only set when a known place was picked.

MySQL also keeps a **generated column** `from_point POINT ... SRID 0`, computed from the
coordinates and stored, which exists only to carry a **SPATIAL index**. Gotchas found while
building it (`migrations/versions/*_free_locations.py`):
- For a generated column MySQL wants `... STORED NOT NULL SRID 0`; `POINT SRID 0 GENERATED ...`
  is a syntax error (found by testing variants on a temporary table).
- The column must have a fixed SRID, or the optimizer won't use the spatial index.
- `POINT(x, y)` takes **longitude first**.

### 5.2 "Rides starting near me"

`trip_service._search_page`, three steps:

1. **Spatial index**: `MBRContains(box, from_point)`, rides whose start lies in a ~2 km
   square around the rider. An R-tree index answers "what's inside this box?" without
   scanning every ride. The box comes from `app/core/geo.py` (`bounding_box_wkt`); a degree
   of longitude shrinks away from the equator, so the box divides by `cos(latitude)`.
2. **Exact circle**: `ST_Distance_Sphere(...) <= 1000` keeps those really within 1 km (the
   index can't evaluate a distance; it only narrows the candidates).
3. **Destination**: the ride ends within 1 km of where the rider is going (same destination)
   or passes it on the way: `detour = dist(start, rider) + dist(rider, end) - dist(start, end)`
   at most 1.5 km, and the rider gets off first.

Each result says how far the rider walks to the host's start (`pickup_distance_m`).

Run `uv run python -m scripts.explain_search` (backend folder). Measured on 30,000 rides
scattered over ~100 km:

| Plan | Rows examined | Time |
|---|---|---|
| No index (full scan, distance computed per row) | ~30,000 | 660 ms |
| Time index only `(status, depart_at)` | 169 | 9.4 ms |
| **SPATIAL index** (MySQL's own choice) | **14** | **4.6 ms** |

The optimizer picked the spatial index by itself because "inside this 2 km box" is far
more selective than "in this 90-minute window".

### 5.3 The frontend

The app is **map-first**, like other ride apps: on the Ride and Offer screens the map fills
the page and the content sits in a sheet over it (a bottom sheet on a phone, a floating
panel on a laptop).

- `frontend/src/components/MapShell.jsx`: that layout. The map is `position: fixed` behind
  everything; the sheet is ordinary page content with space above it, so scrolling the page
  slides the sheet up over the map. No drag-gesture code needed.
- `frontend/src/components/LocationPicker.jsx`: the `useRoutePicker` hook holds the logic
  ("Use my location" via `navigator.geolocation`, tap the map to drop a pin for the active
  field, pick a known place), so the page can connect it to both the form (`RouteFields`,
  `PlaceChips`) and the map. Hosts can rename pins ("Main exit"). If location is blocked (a
  locked-down laptop, a denied permission) the user gets a clear message and taps instead.
- `frontend/src/components/RideMap.jsx`: Leaflet + OpenStreetMap tiles. It keeps the route
  and the found rides inside the part of the map the sheet doesn't cover (`visiblePadding`),
  and draws the route as an arc, because we don't know the real road route.
- `frontend/src/geo.js`: the same haversine distance in JavaScript, and friendly pin names
  ("Near Kulathoor") when a known place is close.
- `frontend/src/styles.css`: one design system. Every colour is a CSS variable (token), so
  dark mode only redefines the tokens. The typeface is bundled with the app
  (`@fontsource-variable/plus-jakarta-sans`) so it also works offline.
- Browsers only share location on **HTTPS** (or localhost), another reason deployment needs
  HTTPS.

**Interview:** *"How would you find nearby drivers (or rides) at scale?"*
Index geography: a SPATIAL (R-tree) index on a POINT column, geohashes in a B-tree, or
Redis GEO commands (`GEOSEARCH`). Filter by a bounding box with the index, then compute exact
distances on the small candidate set. Check with EXPLAIN that the index is actually used.

**Interview:** *"Why not just compute the distance to every row?"*
A distance function on a column can't use a normal index, so MySQL must scan and compute
for every row: 660 ms here at 30,000 rides, growing linearly. The index narrows it to a
handful of candidates first.

---

## Part 6 — Trust and safety

| Feature | Where | Key idea |
|---|---|---|
| Phone OTP | `backend/app/services/phone_service.py` | 6 digits from `secrets`, 5-minute TTL in Redis, HMAC-hashed, 5 attempts, one use; constant-time compare |
| SMS sender | `backend/app/services/sms.py` | Provider behind one function; `console` in dev |
| Ratings | `backend/app/services/rating_service.py` | Only after the host completes the ride, only between its members |
| Rating totals | `backend/app/models/user.py` | Denormalised `rating_sum`/`rating_count`, updated with `SET x = x + n` inside MySQL |
| Block | `backend/app/services/safety_service.py` | Works both ways; filtered after the search cache |
| Share link | `backend/app/services/share_service.py` | 256-bit token, hash stored, expires 6 h after departure; public page shows no contacts |

Why `SET rating_sum = rating_sum + 5` instead of reading, adding in Python and saving: two
ratings arriving at once would both read the same old value and one would be lost (a
"lost update"). The database does the arithmetic atomically.

Why HMAC for OTP codes: six digits are only a million possibilities, so a plain hash in
Redis could be reversed instantly. Keyed with the server secret, it can't.

**Interview:** *"Why denormalise?"*
To make a hot read cheap (a rating next to every search result) at the cost of keeping a
copy in sync on writes. Do it when reads vastly outnumber writes, and update the copy
atomically in the same transaction.

### 6.1 Admins: roles, moderation and suspension

Reports are only useful if someone reads them. `backend/app/services/admin_service.py`,
`backend/app/routers/admin.py`, `frontend/src/pages/Admin.jsx`.

| Idea | Where | Why |
|---|---|---|
| A role in the database | `users.is_admin` | Read on every request (`get_admin_user` in `dependencies/auth.py`), not stored in the token, so removing it works at once |
| Protect the router, not each endpoint | `APIRouter(..., dependencies=[Depends(get_admin_user)])` | An endpoint added later is admin-only by default ("secure by default") |
| No API to become an admin | `backend/app/cli.py` (`python -m app.cli make-admin EMAIL`) | Only someone who can already reach the server can grant it; no endpoint bug can promote a stranger |
| An audit trail | `reports.resolution`, `reviewed_by`, `reviewed_at`, `admin_note` | Moderation must be traceable: who decided what, when and why |
| Suspension takes effect immediately | `get_current_user` rejects a suspended user; refresh tokens are revoked | A JWT can't be recalled, so the database check on each request is what stops a valid token |
| Suspension reuses the normal rules | `_leave_all_rides` calls `cancel_trip` / `cancel_request` | Seats are freed under the same locks, and the others get the usual live alerts |
| Hiding a page is not security | `RequireAuth admin` in `App.jsx` | The Admin tab is hidden from non-admins as a courtesy; the API refuses them regardless |

Authentication answers "who are you?" (401 when it fails). Authorization answers "are you
allowed?" (403 when it fails). `test_admin.py` checks both: no token gives 401, an ordinary
user gets 403.

**Interview:** *"How do you revoke access when you use JWTs?"*
A JWT stays valid until it expires, so: keep access tokens short-lived, revoke the refresh
tokens, and for things that must stop immediately (a suspension) check the database on each
request. That costs one indexed lookup, which this app does anyway to load the user.

**Interview:** *"Where do you check permissions?"*
On the server, at the lowest common point (a dependency on the router), and again in the
service for rules about specific objects ("only the host can cancel"). The frontend hides
what you can't use, but never decides.

---

## Part 6b — Calling outside services (address search and road routes)

`backend/app/services/geo_service.py`, `backend/app/routers/geo.py`,
`frontend/src/useRoadRoute.js`, `PlaceSearch` in `frontend/src/components/LocationPicker.jsx`.

Typing "Mavoor Road" has to become coordinates (**geocoding**), and a line that follows the
streets needs a **routing** service. Both come from OpenStreetMap projects (Nominatim, OSRM).
The browser never calls them: it asks our API, and the API asks them (a **backend proxy**).

| What the proxy buys | How |
|---|---|
| Privacy | The outside service sees our server, not each user's IP; positions are rounded to about 11 m, the search area to about 10 km |
| Speed and lower load | Results are cached for a day in the key-value store (same cache-aside pattern as the ride search) |
| Good manners | At most one search a second (`_wait_for_search_slot` reserves the next slot before sleeping); a per-user rate limit; login required, so strangers can't use us as a free relay |
| Freedom to switch | The provider is a setting (`GEOCODER_URL`, `ROUTING_URL`), not code shipped to every phone |
| Safety against bad data | Every row from outside is validated; a malformed one is dropped instead of breaking the answer |

Three more lessons from this part:

- **Optional features degrade gracefully.** If the service is down, blocked or switched off,
  the API answers 503 with a clear message; the app falls back to tapping the map and draws
  the route as a curve. A nice-to-have must never take the main flow down with it.
- **Respect usage policies in the design.** The free geocoder forbids search-as-you-type, so
  the app searches on Enter or the button, not per keystroke.
- **TLS trust.** HTTPS clients verify servers against a list of trusted certificates. Python
  libraries ship their own list; the API uses the operating system's list instead
  (`ssl.create_default_context()`), which also knows certificates an organisation installs
  on its machines. Never "fix" a certificate error by switching verification off.

Tests replace the one function that goes online (`_get_json`) with a fake, so they are fast,
repeatable and never load someone else's server.

**Interview:** *"How do you integrate a third-party API?"*
Put it behind your own service with a timeout, validation of what comes back, a cache, a
rate limit, and a fallback for when it fails. Keep keys and user data on the server, make
the provider configurable, and fake it in tests.

---

## Part 7 — Shipping it

### 7.1 Docker

- `backend/Dockerfile`: dependencies installed in their own layer (cached until
  `uv.lock` changes), non-root user, `--proxy-headers` so rate limits see real IPs.
- `frontend/Dockerfile`: multi-stage, Node builds the files and only nginx + the files ship.
- `frontend/nginx.conf`: serves the app, forwards `/api` and the WebSocket to the API
  (same origin, so no CORS), single-page-app fallback to `index.html`.
- `docker-compose.yml`: MySQL, Redis, a one-off `migrate` service that runs before the API,
  the API, and nginx.

See `docs/DEPLOYMENT.md` for going live and the production checklist.

### 7.1b Fail fast on unsafe settings, and back up

- `backend/app/core/config.py`: with `ENVIRONMENT=production` the settings object validates
  itself, and the app **refuses to start** with a weak JWT secret, `OTP_DEV_ECHO=true` and
  similar. A loud failure at startup beats a quiet security hole found by a stranger.
  Softer issues (no Redis, a free map server) are logged as warnings.
- `backend/scripts/backup_db.py`: `mysqldump --single-transaction` (one consistent snapshot,
  nobody locked out), compressed, then read back to check it is complete. The password goes
  in a private options file, not on the command line where other users could see it.
  A backup only counts once a restore has been tried.

### 7.2 Continuous integration

`.github/workflows/ci.yml` runs on every push: backend tests against real MySQL and Redis,
`alembic check` (models and migrations agree), a full downgrade to empty and back up (every
migration is reversible), the frontend build, and both Docker image builds.

### 7.3 Testing approach

| Level | Where | What it proves |
|---|---|---|
| Integration tests | `backend/tests/` (pytest + httpx, real MySQL) | Each endpoint's rules, privacy, the last-seat race, rate limits, live events |
| Browser tests | run by hand during development (Playwright + Edge) | The whole flow on a phone-sized screen with two users |
| MCP test | run by hand during development | Tools and resource over real stdio |

---

## Part 8 — AI layer (MCP)

`mcp-server/server.py`, see `mcp-server/README.md`.

- **MCP** (Model Context Protocol) is a standard way to give an AI app tools (functions it
  can call), resources (data it can read) and prompts. Claude Desktop starts the server and
  talks to it over **stdio**, so the server must never print to stdout.
- The server is just another API client: it logs in as the user and refreshes its token.
- Tool design for a model: accept names, not ids ("kulathoor"); return compact, readable
  results (times in IST, fare share already computed); mark read-only tools with
  annotations; raise `ToolError` with a message the model can relay. Other exceptions are
  masked by the SDK so internals don't leak.
- The SDK used is MCP Python SDK 2.x, where `FastMCP` became `MCPServer`. Check the
  installed version before trusting examples written for 1.x.

**Interview:** *"How do you expose an existing API to an LLM safely?"*
Wrap it in narrowly scoped tools with validated inputs, act as the user (their permissions,
not admin), keep the server-side rules the source of truth, require confirmation for
actions that change things, return errors the model can explain, and never put secrets in
tool output.

---

## Bugs found while building (good interview stories)

| Bug | How it was caught | Lesson |
|---|---|---|
| Two people could get the last seat | Concurrency test with the lock removed | Lock the row; test real concurrency |
| Half-applied migration | `Duplicate key name` on retry | MySQL DDL isn't transactional; `alembic stamp` |
| Redundant FK index came back after downgrade | EXPLAIN used the "dropped" index | Check what MySQL actually did |
| Refresh-token reuse not detected | Test with zero grace window | DATETIME rounds to whole seconds |
| Flaky rate-limit test | Passed alone, failed in the full suite | Fixed windows reset at boundaries; freeze the clock |
| New requests invisible until page reload | Browser test | React keeps mounted components; refetch deliberately |
| Stale rating on Profile | Browser test | State loaded at login goes stale |
| Share button did nothing on desktop Edge | Browser test | Always have a fallback for platform APIs |
| `POINT SRID 0 GENERATED ...` syntax error | Migration failed halfway | Test DDL variants on a temporary table first |
| A chained "down then up" command ran after a failed migration and reset local data | My own mistake while building | Run migration steps one at a time and stop at the first error |
| Map didn't zoom to the GPS position | Browser test: a pin landed 12 km away | Leaflet's `fitBounds` ignores a request made during a zoom animation; `flyToBounds` cancels the old move instead. Async results can arrive mid-animation |
| Known places up to 1.3 km off | Looking each one up in OpenStreetMap | Data typed from memory is a guess; check it against a source |
| Search results hidden on a phone | Screenshot: the matches sat under the pinned button | A passing test isn't a usable screen (the test tool scrolls for you); look at it |

## Known gaps (honest list)

- Same-origin `/api` mode behind nginx: one browser test failed on the corporate laptop and
  wasn't diagnosed. Verify with `docker compose` (see `docs/DEPLOYMENT.md`).
- CI runs on every push and passes (tests, frontend build, both Docker images build). The
  full Docker stack running together is still unverified.
- Address search and road routes use free community servers by default. They are fine for
  development; real traffic needs your own or a paid service (see `docs/DEPLOYMENT.md`).
- Driving times come without traffic, so the app says "about".
- No Web Push while the app is closed; SMS uses the dev console.
- A backup restore has not been tried yet (the backup itself was run and verified).
- Lifting a suspension is not recorded anywhere (suspending is, on the report).
