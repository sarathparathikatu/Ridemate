# Deploying RideMate

Everything here is prepared but **not yet tried end to end**: Docker wasn't available on the
laptop the project was built on. Run step 1 on your own machine before deploying anywhere.

## 1. Run the full stack locally with Docker

Needs Docker Desktop (Windows/Mac) or Docker Engine (Linux).

```bash
cp .env.example .env        # then change every value in it
docker compose up --build
```

Open http://localhost:8080. What starts (see `docker-compose.yml`):

| Service | What it is |
|---|---|
| `mysql` | MySQL 8.4 with utf8mb4; data kept in the `mysql-data` volume |
| `redis` | Redis 7: shared cache, rate limits and live events |
| `migrate` | Runs `alembic upgrade head` once, then exits |
| `api` | FastAPI on port 8000 (internal only) |
| `web` | nginx on port 8080: serves the React app and forwards `/api` to `api` |

Check that `/api` works through nginx: register, post a ride in one browser and request it
from a private window. The request should appear live (this exercises the WebSocket proxy).

> Not yet verified: the same-origin `/api` mode (`VITE_API_URL=/api`). The development setup
> (`VITE_API_URL=http://localhost:8000`) passed every browser test; the `/api` mode failed one
> browser test on the corporate laptop for a reason not yet diagnosed. If live updates or
> logins misbehave behind nginx, start by checking `frontend/nginx.conf` and
> `frontend/src/live.jsx` (`WS_URL`).

## 2. Put it on the internet

### Option A: one virtual machine (simplest, cheapest)

Any cloud VM with 1-2 GB RAM (AWS Lightsail, DigitalOcean, Hetzner, Azure, GCP...).

1. Install Docker, `git clone` your repository, create `.env`.
2. `docker compose up -d --build`
3. Point a domain at the VM's IP address.
4. Put **Caddy** in front for automatic HTTPS. Change `web`'s port mapping to
   `"127.0.0.1:8080:80"` so only Caddy is public, then a `Caddyfile` like:

   ```
   ridemate.example.com {
       reverse_proxy 127.0.0.1:8080
   }
   ```

HTTPS is required, not optional: browsers only allow service workers (installable app),
the share sheet and secure cookies on HTTPS.

### Option B: managed services

- **Database**: a managed MySQL 8 (backups and upgrades handled for you).
- **Redis**: a managed Redis.
- **API**: any container platform that supports WebSockets, built from `backend/Dockerfile`.
  Run `alembic upgrade head` as a release/pre-deploy command, not on every container start.
- **Frontend**: build with `VITE_API_URL=https://api.your-domain` and host `dist/` on any
  static host; set the API's `CORS_ORIGINS` to the frontend's URL.

## 3. Production checklist

| Setting | Development | Production |
|---|---|---|
| `JWT_SECRET_KEY` | anything | long random secret, stored as a secret, never in git |
| `OTP_DEV_ECHO` | `true` | **`false`** (otherwise codes are returned to anyone) |
| `SMS_PROVIDER` | `console` | a real provider, added in `backend/app/services/sms.py` |
| `REQUIRE_VERIFIED_PHONE` | `false` | `true` |
| `REDIS_URL` | optional | **required** as soon as there is more than one API process |
| `CORS_ORIGINS` | Vite dev server | only your real site (not needed with the nginx `/api` setup) |

Also:

- **Place coordinates** in `backend/migrations/versions/*_place_coordinates.py` are
  approximate. Check each on a map and fix them with a new migration.
- **Map tiles**: `tile.openstreetmap.org` is fine for testing; for real traffic use a tile
  provider (OpenStreetMap's usage policy limits heavy use).
- **Backups**: schedule MySQL backups (`mysqldump` or the managed service's snapshots) and
  test a restore once.
- **Reports**: users can report each other, but there is no admin screen yet. Review the
  `reports` table and act on it before inviting strangers.
- **Several API processes** (`uvicorn --workers 4` or several containers) need `REDIS_URL`,
  so cache, rate limits and live events are shared between them.
