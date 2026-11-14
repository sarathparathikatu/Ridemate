from fastapi import APIRouter
from sqlalchemy import select

from app.dependencies.db import DbSession
from app.models import Place
from app.schemas.place import PlaceOut

router = APIRouter(prefix="/places", tags=["places"])


@router.get("", response_model=list[PlaceOut])
async def list_places(db: DbSession) -> list[Place]:
    # Public on purpose: the app needs the list to draw its dropdowns before login.
    return list(await db.scalars(select(Place).order_by(Place.kind, Place.name)))
