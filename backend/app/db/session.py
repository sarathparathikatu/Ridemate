from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

# One engine per process; it owns the connection pool.
engine = create_async_engine(
    settings.database_url,
    echo=settings.sql_echo,
    pool_size=5,         # connections kept open
    max_overflow=10,     # extra connections allowed under burst load
    pool_pre_ping=True,  # test a connection before handing it out (survives MySQL restarts)
    pool_recycle=3600,   # replace connections before MySQL's wait_timeout kills them
    connect_args={"init_command": "SET time_zone = '+00:00'"},  # CURRENT_TIMESTAMP in UTC
)

# expire_on_commit=False: objects stay readable after commit; in async code a
# post-commit attribute access would otherwise trigger implicit (forbidden) IO.
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request, always closed afterwards."""
    async with SessionLocal() as session:
        yield session
