# RideMate

Share one auto or cab with people from your train who are going the same way.

Every Monday morning a full train reaches Kazhakoottam station, everyone opens Uber at once,
and cabs run out. RideMate lets you post "arriving at the station ~6:15, going to Kulathoor,
2 seats free", lets others from the same train find you and request to join, and shows the
split fare. Contact details are shared only after the host accepts.

## Stack

| Layer | Tech |
|---|---|
| Frontend | React 19 + Vite, React Router, mobile-first CSS |
| Backend | FastAPI (async), Pydantic, JWT auth (PyJWT), bcrypt |
| Database | MySQL 8 (InnoDB, utf8mb4) via SQLAlchemy 2 async (aiomysql), Alembic migrations |
| Tooling | uv (Python), npm (JS), pytest + httpx |

## Run it locally

Prerequisites: Python 3.12+, [uv](https://docs.astral.sh/uv/), MySQL 8, Node.js LTS.

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

**Tests** (backend, against the local MySQL):
```
cd backend
uv run pytest -v
```

## Project structure

```
backend/
  app/
    core/          config (env vars), security (bcrypt, JWT)
    db/            declarative Base, async engine + session
    models/        SQLAlchemy models: User, Place, Trip, JoinRequest
    schemas/       Pydantic request/response models (public vs private views)
    services/      business rules (trips, join requests, users); no HTTP here
    routers/       thin FastAPI endpoints
    dependencies/  get_current_user (JWT check), DB session
  migrations/      Alembic versions (schema + seed data)
  tests/           integration tests, incl. a concurrency test for the last seat
frontend/
  src/api.js       every HTTP call (attaches the JWT)
  src/auth.jsx     login state (React context)
  src/pages/       Find a ride, Offer a ride, My rides, Login, Register
```

## Design notes

- **Identity comes only from the token.** A trip's host is always the authenticated user,
  never a `host_id` in the request body.
- **Privacy by default.** Search results show a display name only; phone and email are
  returned only to the host and accepted riders.
- **No overbooking.** Accepting a request locks the trip row (`SELECT ... FOR UPDATE`), so two
  simultaneous accepts for the last seat cannot both succeed. `tests/test_rides.py` proves it.
- **UTC in the database.** The API accepts and returns timezone-aware timestamps; the browser
  shows local time.
- **No ID documents, no payments.** Only name, email and an optional phone are stored; the app
  shows the fare split and riders pay the driver directly.
