from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

# Shorthand for endpoints:  async def endpoint(db: DbSession)
DbSession = Annotated[AsyncSession, Depends(get_db)]
