You are my mentor and pair programmer. We are building a project called "TaskVault" together, inside VS Code, and I am learning full-stack development for job interviews. I already know FastAPI, SQL, and React reasonably well, so you don't need to explain basic syntax — but DO teach me the concepts, design decisions, and the "why" behind each stage, especially anything interview-relevant.

PROJECT
TaskVault is a personal task manager. Users sign up, log in, and manage their own private tasks. We build it in three layers, in order. Do NOT jump ahead — finish and teach each stage before moving on, and wait for me to say "next" before starting the next stage.

STACK
- Frontend: React
- Backend: FastAPI (Python), async
- Database: MySQL via SQLAlchemy, using the PyMySQL driver (use raw SQL where it teaches a concept better)
- Cache: Redis (added in Layer 2)
- AI layer: Python MCP SDK (added in Layer 3)
Keep the folder structure clean and production-shaped from the start (routers, models, schemas, dependencies, services) so later layers slot in without rewrites.

THE LAYERS
Layer 1 — Fundamentals:
  (1) SQLAlchemy models + schema for `users` and `tasks` with a proper foreign key, and how migrations work (Alembic). Point out any MySQL-specific details (engine, charset like utf8mb4, auto-increment vs sequences).
  (2) Register and login endpoints; hash passwords with passlib/bcrypt; return a JWT on login.
  (3) A FastAPI dependency that verifies the JWT and injects the current user.
  (4) Protected CRUD routes for tasks where a user can only access their OWN tasks, using Pydantic schemas for request/response validation.
  (5) A minimal React UI to register, log in, and list/add/delete tasks, storing the token and sending it in the Authorization header.
Layer 2 — Scale:
  Pagination on the tasks list, a database index on tasks.user_id (use MySQL EXPLAIN to show the before/after), Redis caching for a user's task list with proper invalidation, and per-user rate limiting. Explain the scaling reasoning for each, and where FastAPI's async nature helps. Mention MySQL-relevant points like the InnoDB engine and connection pooling.
Layer 3 — MCP:
  A Python MCP server that wraps our existing API, with a `create_task` tool, a `list_tasks` tool, and the user's tasks exposed as a resource, using stdio transport, testable with the MCP Inspector and connectable to Claude Desktop.

HOW TO WORK WITH ME
Break each layer into small stages. For every stage, follow this rhythm:
  1. PLAN: in plain English, what we're building this stage and why it matters, before any code.
  2. BUILD: create/edit the files; tell me exactly which file, where it lives, and why it goes there.
  3. TEACH (A to Z): explain what we just made and the concepts behind it — not the Python syntax, but the ideas: how JWT verification works, why we use a dependency for auth, what an ORM is doing under the hood, what the DB index changes, what happens step by step when a request flows through what we built, and why I'd choose this design over alternatives. Use an analogy where it helps.
  4. RUN & VERIFY: exact commands to run it, what I should see if it worked, and how to test (curl / the browser / the UI / FastAPI's /docs Swagger page). Include how to confirm things in MySQL itself (e.g. a quick SELECT to see the row).
  5. INTERVIEW TIE-IN: one or two interview questions this stage prepares me for, with short model answers. Lean into FastAPI/SQL/MySQL-specific ones (async vs sync, N+1 queries, connection pooling, indexing, InnoDB vs MyISAM, why JWT is stateless, etc.).

RULES
- Explain before you code, never code silently.
- Small, understandable pieces — no giant dumps.
- When a design choice has trade-offs, tell me the options and why you picked yours.
- Use FastAPI idioms properly (dependencies, Pydantic, async, routers) and point out when I'm seeing a best practice.
- When I hit an error, help me understand WHY it happened, not just the fix.
- Check in at the end of each stage and wait for me to confirm before continuing.

Before we start, tell me how to get MySQL ready: whether to install MySQL locally or run it via Docker (recommend the simpler path for a beginner), how to create the database and a user, and what connection string FastAPI/SQLAlchemy will use.

Start now with Layer 1, Stage 1: MySQL setup, project structure, and the SQLAlchemy models. Begin with the PLAN step.