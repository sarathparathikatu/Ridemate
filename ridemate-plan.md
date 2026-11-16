# RideMate — project plan

## The problem
Every Monday morning a full train arrives at Kazhakoottam station. Everyone opens Uber at
once, cabs run out, and autos charge high fares. Often someone standing next to you is going
to the same place (e.g. Kulathoor). If you knew that, you could book one ride and split the fare.

## The app
RideMate helps people arriving at the same station, at about the same time, find others going
to the same destination, so one booking serves everyone.

Core flow:
1. A rider posts a trip: station, arrival time, destination, free seats.
   The rider who posts becomes the **host** (the one who books the auto/Uber).
2. Others search: same station, arrival within a time window, same destination.
3. They send a **join request**; the host accepts or declines.
4. Only after acceptance can both sides see each other's name and contact.
5. The app shows the estimated split fare. Payment happens outside the app.

## Stack (unchanged from the original plan)
- Frontend: React
- Backend: FastAPI (async)
- Database: MySQL 8 via SQLAlchemy (aiomysql, built on PyMySQL) + Alembic migrations
- Cache / rate limiting / realtime: Redis
- AI layer: Python MCP SDK (stdio, MCP Inspector, Claude Desktop)
- Package manager: uv

## Data model (first version)
- `users`: id, email, hashed_password, created_at (+ display_name, optional phone in Stage 5)
- `places`: id, name, kind (`station` or `area`); seeded with Kazhakoottam station and nearby areas
- `trips`: id, host user_id, from_place_id, to_place_id, depart_at, flex_minutes, seats_total,
  seats_taken, vehicle (auto/cab/any), status (open/full/cancelled/completed), timestamps
- `join_requests`: id, trip_id, requester user_id, seats, status (pending/accepted/declined/cancelled),
  created_at; one request per user per trip

## Privacy and safety rules (built in from day one)
- Contact details stay hidden until a join request is accepted.
- Store only what's needed: name, email, optional phone. No government ID documents.
- No payment handling: show the split, never collect card or bank details.

## Layers and stages

### Layer 1: Fundamentals
1. ✅ MySQL setup, project structure, SQLAlchemy models, Alembic (first migration)
2. ✅ Register + login, bcrypt password hashing, JWT
3. ✅ JWT secret in .env; register/login working
4. ✅ Current-user dependency (`get_current_user`, `CurrentUser`) + protected `GET /users/me`
5. ✅ New migration: drop `tasks`, add `places` (+ seed data), `trips`, `join_requests`;
   add user display_name (3-step backfill) + phone
6. ✅ Trip CRUD (only the host can edit/cancel) + match search (others' trips, limited fields)
7. ✅ Join requests: request / accept / decline / cancel; contact revealed only after acceptance;
   safe seat booking with `SELECT ... FOR UPDATE` (race test proves no overbooking)
8. ✅ React (Vite) mobile-first UI: register, login, find, offer, my rides; browser E2E verified

## Status: all phases built

| Phase | Status | Commit message starts with |
|---|---|---|
| A: refresh tokens, live notifications, PWA | ✅ built, browser-tested | "Phase A" |
| B: pagination, search index + EXPLAIN, Redis cache, rate limits (Layer 2) | ✅ built, tested | "Phase B" |
| C: map, "on the way" matching | ✅ built, browser-tested | "Phase C" |
| D: phone OTP, ratings, report/block, share with family | ✅ built, browser-tested | "Phase D" |
| E: Docker, CI, deployment guide | ✅ written; runs on first push / with Docker | "Phase E" |
| F: MCP server for Claude Desktop (Layer 3) | ✅ built, tested over stdio | "Phase F" |
| Option 2: any location in any city (GPS, map pins, SPATIAL index) | ✅ built, browser-tested in Kozhikode | "Any location" |
| Redesign: map-first ride app UI (bottom sheet, ride options, dark mode) | ✅ built, browser-tested on phone and laptop sizes | "Redesign" |
| Admin screen: review reports, suspend accounts, audit trail | ✅ built, tested (API + browser) | "Admin screen" |
| Address search and road routes (OpenStreetMap services behind the API) | ✅ built, tested (fakes in tests, real services in the browser) | "Admin screen" |
| Corrected place coordinates, production settings checks, backup script | ✅ built; restore not yet tried | "Admin screen" |

Still to do (all need a machine with Docker, a cloud account, or a paid service): verify the
Docker / same-origin `/api` setup, deploy with HTTPS, add a real SMS provider, try a backup
restore, and Web Push for notifications while the app is closed.
Study material: docs/SIMPLE-GUIDE.md first, then docs/LEARNING-GUIDE.md.

The original Layer 2 and Layer 3 notes below are kept for reference.

### Layer 2: Scale
- Pagination on match search
- Composite index on trips for the search query; MySQL `EXPLAIN` before/after; column order
  and the leftmost-prefix rule
- Redis cache for "open trips at station X in the next 2 hours", with invalidation on
  post / cancel / accept
- Per-user rate limiting on join requests
- InnoDB, connection pooling, where async helps (many searches when a train arrives)
- Location matching: MySQL spatial types (`POINT`, `ST_Distance_Sphere`) for "on the way" matches
- Optional: live notifications with WebSockets + Redis pub/sub

### Layer 3: MCP
- MCP server wrapping the API, stdio transport
- Tools: `find_co_travellers`, `post_trip`, `request_to_join`
- Resource: the user's upcoming trips
- Test with MCP Inspector, connect to Claude Desktop

## How we work (same rhythm as plan.md)
For every stage: PLAN → BUILD → TEACH → RUN & VERIFY → INTERVIEW TIE-IN.
Small pieces, explain before coding, trade-offs stated, wait for "next" before moving on.
