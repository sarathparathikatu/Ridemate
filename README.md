# RideMate

Share one auto or cab with people from your train who are going the same way.

Every Monday morning a full train reaches Kazhakoottam station, everyone opens Uber at once,
and cabs run out. RideMate lets you post "arriving at the station ~6:15, going to Kulathoor,
2 seats free". Others from the same train find you (even if they're getting off on the way),
request to join, and split the fare. Contact details are shared only after the host accepts.

The [early concept screens (PDF)](docs/RideMate-concept.pdf) show where the design started;
the app has since moved to a map-first layout.

## Features

- **Works in any city**: rides start and end anywhere (phone GPS, a pin on the map, or a
  known place). "Rides starting near me" uses a MySQL **SPATIAL index**, plus
  **"on the way"** matches computed with `ST_Distance_Sphere`; Leaflet + OpenStreetMap map.
- **Join requests**: request, accept, decline, cancel; row locking guarantees the last seat
  can't be given twice.
- **Live updates**: WebSockets (Redis pub/sub across server processes), toasts and
  background-tab notifications.
- **Accounts**: bcrypt passwords, short JWT access tokens, rotating refresh tokens with
  reuse detection.
- **Trust & safety**: phone verification by OTP, ratings after a completed ride, report and
  block, share-with-family links, contacts hidden until a request is accepted.
- **Scale**: keyset pagination, spatial and composite indexes (EXPLAIN demo: 660 ms -> 4.6 ms),
  Redis cache with versioned invalidation, per-user and per-IP rate limits.
- **Map-first design**: the map fills the screen and everything sits in a sheet over it
  (bottom sheet on phones, floating panel on laptops); dark mode; installable as a PWA.
- **AI**: an MCP server so Claude Desktop can find, post and join rides for you.

## Stack

| Layer | Tech |
|---|---|
| Frontend | React 19 + Vite, React Router, Leaflet, PWA |
| Backend | FastAPI (async), Pydantic, PyJWT, bcrypt, WebSockets |
| Data | MySQL 8 (InnoDB, utf8mb4) via SQLAlchemy 2 async + Alembic; Redis (optional locally) |
| AI | MCP Python SDK 2.x (stdio server) |
| Tooling | uv, npm, pytest + httpx, Docker, GitHub Actions |

## Run it locally (development)

Prerequisites: Python 3.12+, [uv](https://docs.astral.sh/uv/), MySQL 8, Node.js LTS.
Redis is optional locally: without `REDIS_URL` the cache, rate limits and live events live
in the server's memory.

**1. Database** (once, as MySQL root):
```
mysql -u root -p -e "source backend/sql/01_create_db_and_user.sql"
```

**2. Backend**:
```
cd backend
cp .env.example .env        # then set the DB password and a JWT_SECRET_KEY
uv sync
uv run alembic upgrade head # creates tables and seeds places
uv run uvicorn app.main:app --reload
```
API docs: http://127.0.0.1:8000/docs

**3. Frontend** (second terminal):
```
cd frontend
npm install
npm run dev
```
App: http://localhost:5173

Phone verification in development: no SMS is sent; the code is printed in the backend
terminal and shown on the Profile page (`OTP_DEV_ECHO=true`).

## Run the whole stack with Docker

```
cp .env.example .env    # set the secrets
docker compose up --build
```
App: http://localhost:8080. Details and going live: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Tests

```
cd backend
uv run pytest -v
```
26 integration tests against the real MySQL, including concurrent accepts for the last
seat, refresh-token theft detection, live WebSocket events (in-process and via Redis), rate
limits, "on the way" matching, OTP and blocking. CI runs them on every push with real MySQL
and Redis, plus a migration drift check and a full rollback.

Index demo: `uv run python -m scripts.explain_search` (backend folder).

## Project structure

```
backend/
  app/
    core/          settings, security (bcrypt, JWT), Redis client, key-value store
    db/            declarative Base, async engine + session
    models/        User, Place, Trip, JoinRequest, RefreshToken, Rating, Report, Block, TripShare
    schemas/       Pydantic request/response models (public vs private views, pagination)
    services/      business rules: trips, requests, tokens, phone, ratings, safety, sharing
    routers/       thin FastAPI endpoints (+ /ws WebSocket)
    realtime/      WebSocket connections and the event broker
    dependencies/  current user, verified user, DB session, rate limits
  migrations/      Alembic versions (schema + seed data)
  tests/           integration tests
  scripts/         learning demos (ORM, JWT, EXPLAIN)
frontend/
  src/api.js       every HTTP call (tokens, silent refresh, pagination)
  src/live.jsx     WebSocket connection, toasts, notifications
  src/pages/       Find a ride, Offer a ride, My rides, Profile, Share, Login, Register
  public/          PWA manifest, service worker, icons
mcp-server/        MCP server for Claude Desktop (see its README)
docs/              LEARNING-GUIDE.md, DEPLOYMENT.md, concept screens
```

## Design notes

- **Identity comes only from the token**: a ride's host is always the authenticated user.
- **Privacy by default**: search shows a name, badge and rating; phone and email only reach
  people inside an accepted ride; share links never show contacts.
- **No ID documents, no payments**: name, email and an optional verified phone; the app
  shows the fare split and riders pay the driver directly.
- **UTC in the database**: the API accepts and returns timezone-aware timestamps.

Everything is explained concept by concept in [docs/LEARNING-GUIDE.md](docs/LEARNING-GUIDE.md).
