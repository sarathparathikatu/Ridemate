# RideMate in simple words

Every idea used in this project, explained for someone meeting it for the first time.
Each one has four lines:

- **Problem**: why the idea exists.
- **Picture**: something from everyday life that works the same way.
- **In RideMate**: what the app actually does.
- **Remember**: one line to keep.

Read it top to bottom once. For more depth and interview questions, continue with
[LEARNING-GUIDE.md](LEARNING-GUIDE.md).

---

## Part 1. The big picture

### 1. Three parts: frontend, backend, database
- **Problem**: an app has to show screens, apply rules and remember things.
- **Picture**: a restaurant. The dining hall is what you see, the kitchen is where the work
  follows rules, and the store room is where things are kept.
- **In RideMate**: the dining hall is the **frontend** (React, in `frontend/`). The kitchen
  is the **backend** (FastAPI, in `backend/`). The store room is the **database** (MySQL).
  The frontend never touches the database; it always asks the backend.
- **Remember**: screens in front, rules in the middle, data at the back.

### 2. API, request, response, status code
- **Problem**: the frontend and backend need an agreed way to talk.
- **Picture**: a menu and a waiter. You order from the menu (a **request**). The waiter brings
  the dish, or says "not available" (a **response**).
- **In RideMate**: the **API** is the menu: the list of things the backend agrees to do, such
  as `GET /trips/search` or `POST /trips`. Data travels as **JSON**, which is plain text like
  `{"seats": 2}`. Every response starts with a **status code**:

  | Code | Meaning in plain words |
  |---|---|
  | 200, 201 | Done. (201 = something new was created) |
  | 400 | Your request doesn't make sense |
  | 401 | I don't know who you are (log in) |
  | 403 | I know who you are, but you're not allowed |
  | 404 | That thing doesn't exist |
  | 409 | It clashes with the current state (the seat is already taken) |
  | 422 | A field has the wrong shape (text where a number should be) |
  | 429 | Too many requests, slow down |
  | 503 | Something we depend on is not answering |

- **Remember**: an API is a menu; a status code is the waiter's first word.

### 3. Layers inside the backend
- **Problem**: if everything is in one file, every change breaks something else.
- **Picture**: a hospital. Reception takes your slip, the doctor decides, the records room
  stores your file. Each has one job.
- **In RideMate**: a **router** receives the request (reception). A **service** holds the
  rules, like "only the host can cancel" (the doctor). A **model** describes a table (the
  records room). A **schema** is the form that says which fields may come in and go out, so
  a password can never leak by accident.
- **Where**: `backend/app/routers`, `services`, `models`, `schemas`.
- **Remember**: one job per layer.

### 4. SQLAlchemy and Alembic
- **Problem**: writing raw SQL everywhere is slow and error-prone, and tables change over time.
- **Picture**: SQLAlchemy is a translator: you speak Python, it speaks SQL to the database.
  Alembic is a numbered set of instruction sheets for changing the building: "sheet 7: add a
  room". Everyone follows the same sheets in the same order and ends with the same building.
- **In RideMate**: a Python class `Trip` is the `trips` table, and one ride is one object
  (`trip.seats_taken`). Each change to the tables is a **migration** file that can be applied
  (upgrade) and undone (downgrade). Adding a required column to a table that already has rows
  takes three steps: add it as optional, fill it in, then make it required.
- **Where**: `backend/app/models`, `backend/migrations/versions`.
- **Remember**: SQLAlchemy talks to the tables; Alembic changes the tables.

### 5. Async
- **Problem**: while the database is busy with one request, the server shouldn't make
  everyone else wait.
- **Picture**: one waiter, many tables. While table 1's food is cooking, he takes table 2's
  order instead of standing at the kitchen door.
- **In RideMate**: FastAPI and the database driver are **async**, so one server process
  handles many people at once. Heavy work that would block the waiter (checking a password)
  is handed to a helper.
- **Remember**: async means never waiting idle.

---

## Part 2. Accounts and security

### 6. Password hashing
- **Problem**: if the database is ever stolen, the passwords must not be in it.
- **Picture**: a mixer. You can turn fruit into juice, but never juice back into fruit. At
  login we blend what you typed and compare the juice.
- **In RideMate**: **bcrypt** turns a password into a hash. It is slow on purpose (guessing
  millions of passwords becomes expensive) and adds random "salt", so two people with the
  same password get different hashes.
- **Where**: `backend/app/core/security.py`.
- **Remember**: store the juice, never the fruit.

### 7. JWT access token
- **Problem**: after login the server must know who sent each request, without asking for
  the password every time.
- **Picture**: a wristband at an exhibition, stamped with a seal only the organiser has. The
  guard checks the seal; he doesn't phone the office.
- **In RideMate**: the token holds your user id and an expiry time (30 minutes), plus a
  **signature** made with the server's **secret key**. Anyone can read a token; nobody can
  change one without breaking the signature. There is one secret key for the whole server,
  not one per user.
- **Remember**: a JWT is a signed pass that expires.

### 8. Refresh token
- **Problem**: a 30-minute pass is safe but would log you out all day long.
- **Picture**: a counter slip that gets you a fresh wristband. Each slip works once, and you
  get a new slip with every new wristband. If an old slip turns up again, someone copied it,
  so every slip from that login is cancelled.
- **In RideMate**: refresh tokens last 30 days, are stored only as hashes, are swapped on
  every use (**rotation**), and reuse of an old one ends that login for everyone holding it.
- **Where**: `backend/app/services/token_service.py`.
- **Remember**: a short pass to work, a slip to renew, and a used slip is an alarm.

### 9. Authentication and authorization
- **Problem**: knowing who someone is does not mean they may do everything.
- **Picture**: an office. Your ID card gets you into the building (who are you?). It doesn't
  open the cash room (are you allowed?).
- **In RideMate**: **authentication** fails with 401, **authorization** with 403. Who you are
  comes only from the token, never from what the request claims. Only the host can cancel a
  ride. Phone and email are shown only to people inside an accepted ride.
- **Remember**: first identify, then permit.

### 10. Admins, suspension and the audit trail
- **Problem**: users can report each other, but a report is useless if nobody reads it.
- **Picture**: a housing society's complaint register. A committee member reads each
  complaint and writes the decision, their name and the date beside it.
- **In RideMate**: an account can be marked as **admin**, and only from the server's command
  line (`python -m app.cli make-admin EMAIL`), never through the app. Admins see the reports
  and choose Dismiss or Suspend. The decision is written on the report: who, when and why
  (the **audit trail**). A suspended person is logged out at once, their rides are cancelled
  and their seats in other rides are freed. It can be lifted later.
  The Admin tab is hidden from everyone else, but the real lock is on the server.
- **Where**: `backend/app/services/admin_service.py`, `frontend/src/pages/Admin.jsx`.
- **Remember**: hide the door in the app, lock it on the server, write down every decision.

---

## Part 3. Rides

### 11. Trips, join requests and privacy
- **Problem**: strangers must be able to find each other without exposing phone numbers.
- **Picture**: a notice board. Anyone can read "going to Kulathoor at 6:15, 2 seats". You
  swap numbers only after both agree.
- **In RideMate**: a **host** posts a trip. A rider sends a **join request**. The host
  accepts or declines. Before acceptance you see a name, a badge and a rating. After it,
  both sides see phone and email.
- **Remember**: share the minimum until both sides agree.

### 12. The last seat (race condition and row lock)
- **Problem**: one seat is left and two requests are accepted in the same instant. Both read
  "1 seat left", both succeed, and the ride is overbooked. This is a **race condition**.
- **Picture**: one train ticket, two counters. The fix: only one clerk may hold the ticket
  register at a time. The second waits, then sees "0 left".
- **In RideMate**: accepting a request first **locks** that ride's row in MySQL
  (`SELECT ... FOR UPDATE`). A test fires accepts at the same moment and proves only one wins.
- **Where**: `backend/app/services/request_service.py`.
- **Remember**: "check, then change" must happen as one step.

### 13. Time zones
- **Problem**: "6:15" means different moments in different places.
- **Picture**: a railway uses one official clock, and each station shows local time.
- **In RideMate**: the database stores every time in **UTC**. The browser shows it in your
  local time. A time sent without a zone is rejected.
- **Remember**: one clock in the database, local clocks on screens.

---

## Part 4. Speed and scale

### 14. Pagination
- **Problem**: a search might match thousands of rides. Sending them all is slow and pointless.
- **Picture**: a bookmark. You open the book where you stopped; you don't count pages from
  the start.
- **In RideMate**: the server sends 20 rides and a **cursor** (the bookmark: the last ride's
  time and id). "Load more" sends the cursor back. It asks the database for 21 rows, so it
  knows whether a next page exists.
- **Where**: `backend/app/schemas/pagination.py`.
- **Remember**: small pages, and a bookmark to continue.

### 15. Indexes
- **Problem**: without help, the database reads every row to find a few.
- **Picture**: the index at the back of a book. A phone directory sorted by city, then name,
  helps you search by city, or by city and name, but not by name alone. For places, think of
  a map cut into squares: you only look in the squares near you.
- **In RideMate**: an ordinary index speeds up searching by status and time. A **spatial
  index** finds rides that start near you. `EXPLAIN` asks MySQL how it plans to find the
  rows. Result on 30,000 rides: 660 ms without the index, 4.6 ms with it.
- **Where**: `backend/app/models/trip.py`, `backend/scripts/explain_search.py`.
- **Remember**: an index lets the database jump instead of read.

### 16. Caching
- **Problem**: when a train arrives, hundreds of people run nearly the same search.
- **Picture**: an enquiry counter. The clerk looks up the answer once and writes it on a
  whiteboard. Everyone else reads the board.
- **In RideMate**: the first search asks MySQL and saves the answer for 30 seconds. When
  anything changes (a new ride, a seat taken), a "board number" goes up, so all old answers
  stop being used at once. The cache is only for showing rides. Whether you really get the
  seat is decided by the database.
- **Where**: `backend/app/services/trip_service.py`.
- **Remember**: write an answer down once, reuse it, and throw it away when it may be old.

### 17. Rate limiting
- **Problem**: someone could try 10,000 passwords, or press "send code" 500 times.
- **Picture**: an ATM blocks the card after three wrong PINs.
- **In RideMate**: the server counts actions per person per time window, for example 10
  login tries a minute and 3 codes per 10 minutes. Over the limit, it answers 429 and says
  how long to wait.
- **Where**: `backend/app/dependencies/rate_limit.py`.
- **Remember**: count how often, and say "wait" when it's too often.

### 18. Redis
- **Problem**: with several copies of the server running, each would keep its own cache and
  its own counters.
- **Picture**: one shared notebook on the counter, with notes that erase themselves after a
  set time.
- **In RideMate**: Redis holds the cache, the rate-limit counters and the live-event channel.
  On a laptop with one server, plain memory is used instead.
- **Remember**: one shared notebook for all servers.

---

## Part 5. Live updates and the installed app

### 19. WebSockets and publish/subscribe
- **Problem**: the host should see a join request the moment it is sent, without refreshing.
- **Picture**: ordinary requests are letters: you write, you get a reply. A **WebSocket** is
  a phone call that stays open, so either side can speak at any time. With several servers,
  think of the station loudspeaker: one announcement, heard on every platform.
- **In RideMate**: each open app keeps one WebSocket to the server. When something happens,
  the server announces it on a Redis channel (**publish**), every server hears it
  (**subscribe**) and tells its own connected users. If the line drops, the app redials,
  waiting a little longer each time.
- **Where**: `backend/app/realtime`, `frontend/src/live.jsx`.
- **Remember**: keep a line open, and announce to every server.

### 20. PWA (installable web app)
- **Problem**: people want an icon on the phone and an app that opens fast, without an app store.
- **Picture**: a visiting card (name, logo, colours) plus a helper who keeps a copy of the
  shop's layout so the door opens even when the network is bad.
- **In RideMate**: the **manifest** is the visiting card. The **service worker** is the
  helper: it keeps the app's own files, never ride data, which must always be fresh.
- **Where**: `frontend/public/manifest.webmanifest`, `frontend/public/sw.js`.
- **Remember**: a website that installs like an app.

---

## Part 6. Maps

### 21. Places and distance
- **Problem**: "near me" and "on my way" must be worked out by a computer.
- **Picture**: every spot on Earth has two numbers, like a row and a column: **latitude** and
  **longitude**.
- **In RideMate**: each ride stores the two numbers for its start and its end. "Near me"
  first uses the spatial index to pick rides in a small square around you, then measures the
  exact distance (within 1 km). "On the way" means dropping you adds only a small detour
  (up to 1.5 km).
- **Where**: `backend/app/services/trip_service.py`, `backend/app/core/geo.py`.
- **Remember**: narrow down with the index, then measure exactly.

### 22. Address search and road routes
- **Problem**: people type "Technopark", not numbers. And a straight line is not a road.
- **Picture**: you ask the hotel reception to phone a taxi company. The taxi company hears
  from the hotel, not from you. Reception also remembers the answer for the next guest.
- **In RideMate**: **geocoding** turns a typed name into the two numbers. **Routing** finds
  the road path, its length and the driving time. Both come from OpenStreetMap services, and
  the browser never calls them: it asks our API, and the API asks them. That gives privacy
  (they see our server, not you), speed (answers are remembered for a day), good manners (at
  most one search a second) and freedom (the provider is just a setting). If the service
  doesn't answer, the app still works: you tap the map, and the route is drawn as a curve.
- **Where**: `backend/app/services/geo_service.py`, `frontend/src/useRoadRoute.js`.
- **Remember**: let your server talk to outsiders, remember their answers, and keep working
  when they are silent.

### 23. Map-first design
- **Problem**: a ride app that looks like a form doesn't feel like a ride app.
- **Picture**: a map on the table with a notepad lying on top of it.
- **In RideMate**: the map fills the screen. Everything else sits in a sheet over it: it
  slides up from the bottom on a phone and floats on the left on a laptop.
- **Where**: `frontend/src/components/MapShell.jsx`, `frontend/src/styles.css`.
- **Remember**: in a ride app, the map is the page.

---

## Part 7. Trust and safety

### 24. OTP (one-time code)
- **Problem**: anyone can type any phone number. The app must check that it is really yours.
- **Picture**: the 6-digit code a bank texts you. It works for a few minutes, a few tries,
  and only once.
- **In RideMate**: the code lives 5 minutes, allows 5 wrong guesses and is used once. It is
  stored scrambled with the server's secret, not as plain digits. Only 3 codes can be sent
  per 10 minutes, because every text costs money.
- **Where**: `backend/app/services/phone_service.py`.
- **Remember**: short life, few tries, one use.

### 25. Ratings, block, report and share link
- **Problem**: sharing a vehicle with a stranger needs signals of trust and a way out.
- **Picture**: reviews on a shop, a "do not disturb" list, a complaint box, and telling your
  family which bus you took.
- **In RideMate**: you can rate only after a completed ride, and only people who were in it.
  The totals are kept on the person's row, so "4.8 (12)" shows instantly. **Block** works
  both ways. A **report** goes to the admins. A **share link** lets family see the route and
  time, never contacts; it is a long random secret, and the server stores only its hash.
- **Remember**: every safety feature shares less, not more.

---

## Part 8. Shipping and running it

### 26. Settings, secrets and production checks
- **Problem**: passwords and keys must not sit in the code, and a setting meant for testing
  must never reach real users.
- **Picture**: a safety switch at home. With faulty wiring it trips at once, rather than
  letting you find out by touching the wire.
- **In RideMate**: settings come from **environment variables** (a `.env` file that git
  ignores). With `ENVIRONMENT=production` the app **refuses to start** if the secret key is
  weak or a testing convenience is still switched on.
- **Where**: `backend/app/core/config.py`.
- **Remember**: a loud failure at startup beats a quiet hole later.

### 27. Tests
- **Problem**: every change can break something that used to work.
- **Picture**: a checklist a pilot runs before every flight.
- **In RideMate**: 42 automatic tests call the real app with a real MySQL. Outside map
  services are replaced by pretend ones, so tests are fast and never bother anyone else's
  server. Browser tests click through the app as two or three people at once.
- **Where**: `backend/tests`.
- **Remember**: tests let you change code without fear.

### 28. Docker
- **Problem**: "it works on my machine" but not on the server.
- **Picture**: a tiffin carrier: the meal and everything it needs, packed together, the same
  wherever you open it.
- **In RideMate**: each part is packed as a **container**: the code together with the exact
  versions it needs. `docker compose` starts MySQL, Redis, the migrations, the API and the
  website with one command.
- **Where**: `backend/Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml`.
- **Remember**: pack the app together with its surroundings.

### 29. CI (continuous integration)
- **Problem**: people forget to run the tests.
- **Picture**: an inspector who checks every delivery, every time, without being asked.
- **In RideMate**: on every push, GitHub runs the tests with real MySQL and Redis, checks
  that the migrations match the code and can be undone, builds the website and builds both
  containers. It already caught one bug that only appeared on Linux.
- **Where**: `.github/workflows/ci.yml`.
- **Remember**: every push is checked by a machine.

### 30. Backups
- **Problem**: one bad command or one dead disk can erase everything.
- **Picture**: a photocopy of the account register, kept in another building. It only counts
  if you have tried reading from the photocopy.
- **In RideMate**: one command makes a compressed copy of the database, checks that the copy
  is complete and keeps the newest few. Loading a copy into a spare database (a **restore**)
  still has to be tried once.
- **Where**: `backend/scripts/backup_db.py`.
- **Remember**: a backup counts only after a restore has worked.

### 31. MCP (tools for an AI assistant)
- **Problem**: you want to say "find me a ride to Kulathoor at 6" to an assistant, safely.
- **Picture**: you give a helper a few labelled buttons, not the keys to the office.
- **In RideMate**: an **MCP server** offers Claude Desktop five tools (list places, find
  co-travellers, post a ride, request to join, show my rides). It logs in as you, so it can
  do only what you can do.
- **Where**: `mcp-server/server.py`.
- **Remember**: give an AI narrow tools, not full access.

---

## The project in one minute

Say this when an interviewer asks "tell me about your project":

> RideMate helps people arriving at the same railway station share one auto or cab. A host
> posts a ride, people nearby who are going the same way ask to join, and contact details
> are shared only after the host accepts. It is a React app with a FastAPI backend and MySQL.
> The parts I learned most from: locking a row so the last seat can't be given twice, a
> spatial index that took "rides near me" from 660 ms to 4.6 ms, a Redis cache and rate
> limits, live updates over WebSockets, logins with rotating refresh tokens, an admin flow
> with an audit trail, and CI that runs 42 tests on every push.

Then expect "how does X work?" for any one of those. The answers are above.
