from fastapi import APIRouter

from app.dependencies.db import DbSession
from app.schemas.safety import ShareView
from app.services import share_service

router = APIRouter(prefix="/share", tags=["share"])


@router.get("/{token}", response_model=ShareView)
async def view_shared_ride(token: str, db: DbSession) -> ShareView:
    """Public on purpose (no login): family opens the link. The secret token is the key."""
    return await share_service.view(db, token)
