import asyncio
import contextlib
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.redis import get_redis
from app.db.session import engine, get_db
from app.realtime.broker import relay_forever
from app.routers import auth, places, requests, trips, users, ws
from app.services.errors import DomainError


@asynccontextmanager
async def lifespan(app: FastAPI):
    relay = asyncio.create_task(relay_forever())  # Redis events -> this process's sockets
    yield
    relay.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await relay
    if (redis := get_redis()) is not None:
        await redis.aclose()
    await engine.dispose()  # close pooled MySQL connections on shutdown


app = FastAPI(title="RideMate", lifespan=lifespan)

# The React app runs on another origin (port 5173); browsers block such calls unless the
# API explicitly allows that origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    # Services raise NotFoundError / ForbiddenError / ConflictError; this one place maps
    # them to 404 / 403 / 409, so no endpoint needs its own try/except.
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(places.router)
app.include_router(trips.router)
app.include_router(requests.router)
app.include_router(ws.router)


@app.get("/health")
async def health(db: Annotated[AsyncSession, Depends(get_db)]) -> dict[str, str]:
    version = await db.scalar(text("SELECT VERSION()"))
    return {"status": "ok", "mysql_version": version}
