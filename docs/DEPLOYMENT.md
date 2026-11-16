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

HTTPS is required, not optional: browsers only allow location ("Use my location"),
service workers (installable app), the share sheet and secure cookies on HTTPS.

### Option B: managed services

- **Database**: a managed MySQL 8 (backups and upgrades handled for you).
- **Redis**: a managed Redis.
- **API**: any container platform that supports WebSockets, built from `backend/Dockerfile`.
  Run `alembic upgrade head` as a release/pre-deploy command, not on every container start.
- **Frontend**: build with `VITE_API_URL=https://api.your-domain` and host `dist/` on any
  static host; set the API's `CORS_ORIGINS` to the frontend's URL.

## 3. Production checklist

Set `ENVIRONMENT=production`. The API then **refuses to start** with settings that would put
real users at risk (a short or placeholder `JWT_SECRET_KEY`, `OTP_DEV_ECHO=true`,
`REQUIRE_VERIFIED_PHONE=true` without a real SMS provider, `CORS_ORIGINS=*`), and logs a
warning for things worth a second look. The rules are in `backend/app/core/config.py`.

| Setting | Development | Production |
|---|---|---|
| `ENVIRONMENT` | `development` | **`production`** (turns the checks on) |
| `JWT_SECRET_KEY` | anything | long random secret, stored as a secret, never in git |
| `OTP_DEV_ECHO` | `true` | **`false`** (otherwise codes are returned to anyone) |
| `SMS_PROVIDER` | `console` | a real provider, added in `backend/app/services/sms.py` |
| `REQUIRE_VERIFIED_PHONE` | `false` | `true` |
| `REDIS_URL` | optional | **required** as soon as there is more than one API process |
| `CORS_ORIGINS` | Vite dev server | only your real site (not needed with the nginx `/api` setup) |
| `OUTBOUND_USER_AGENT` | generic default | your site's name or a contact address |
| `GEOCODER_URL`, `ROUTING_URL` | free community servers | your own or a paid service once traffic grows |

Also:

- **Several API processes** (`uvicorn --workers 4` or several containers) need `REDIS_URL`,
  so cache, rate limits and live events are shared between them.
- **Map tiles**: `tile.openstreetmap.org` is fine for testing; for real traffic use a tile
  provider (OpenStreetMap's usage policy limits heavy use).

## 4. Admins and reports

Users can report each other. Someone has to read those reports, so make yourself an admin
once the app is running. Admin rights are given from the command line, never through the API:

```bash
docker compose exec api python -m app.cli make-admin you@example.com
# without Docker, from the backend folder:
uv run python -m app.cli make-admin you@example.com
```

Log in again and an **Admin** tab appears: open reports, reviewed reports (with who decided
and why), and suspended accounts. Suspending an account logs that person out, cancels their
rides and frees their seats in other rides; it can be lifted later. `revoke-admin` and
`list-admins` work the same way.

## 5. Backups

A backup you have never restored is only a hope. Do both steps once before you have users.

```bash
# without Docker, from the backend folder (keeps the newest 14 files in backend/backups/):
uv run python -m scripts.backup_db --keep 14
uv run python -m scripts.backup_db --verify backups/<file>.sql.gz

# with Docker:
docker compose exec -T mysql sh -c 'mysqldump --single-transaction --no-tablespaces \
  -u ridemate -p"$MYSQL_PASSWORD" ridemate' | gzip > ridemate-$(date +%F).sql.gz
```

Schedule it daily (cron or Task Scheduler) and copy the files to another machine: a backup on
the same disk protects against mistakes, not against losing the disk. To test a restore,
load a backup into a spare database and look at it:

```bash
mysql -u root -p -e "CREATE DATABASE restore_test"
gunzip -c ridemate-<date>.sql.gz | mysql -u root -p restore_test
```

The backup script was run and verified on the development laptop; the restore step and the
Docker command above have not been tried yet.

## 6. Outside map services

Two features ask outside services for help, always through the API, never from the browser:

| Feature | Setting | Default | What is sent |
|---|---|---|---|
| Address search | `GEOCODER_URL` | OpenStreetMap Nominatim | the text someone typed, and a rough area (about 10 km) |
| Road route, distance, time | `ROUTING_URL` | the public OSRM demo server | the two ends of a route, rounded to about 11 m |

No name, account or IP address of a user is sent: the outside service only sees your server.
Results are cached for a day. Both features are extras: with a URL left empty (or the
service down) people set places by GPS or by tapping the map, and the route is drawn as a
simple curve.

The defaults are **free community servers** with usage policies: identify your app
(`OUTBOUND_USER_AGENT`), cache results, at most about one search a second, and no
search-as-you-type (which is why the app searches only when asked). They are right for
development and small projects. For real traffic, run your own (both are open source) or use
a paid provider that speaks the same API, and tell your users in your privacy notice.

Known places' coordinates come from OpenStreetMap
(`backend/migrations/versions/*_correct_place_coordinates.py`).
