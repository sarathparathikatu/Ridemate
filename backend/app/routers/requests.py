from typing import Annotated

from fastapi import APIRouter, Query

from app.dependencies.auth import CurrentUser
from app.dependencies.db import DbSession
from app.schemas.join_request import IncomingRequestOut, MyRequestOut
from app.schemas.pagination import DEFAULT_LIMIT, MAX_LIMIT, Page
from app.services import request_service

router = APIRouter(prefix="/requests", tags=["requests"])


@router.get("/mine", response_model=Page[MyRequestOut])
async def my_requests(
    db: DbSession,
    current_user: CurrentUser,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
) -> Page[MyRequestOut]:
    return await request_service.list_my_requests(db, current_user, cursor, limit)


@router.post("/{request_id}/accept", response_model=IncomingRequestOut)
async def accept(request_id: int, db: DbSession, current_user: CurrentUser) -> IncomingRequestOut:
    return IncomingRequestOut.build(
        await request_service.accept_request(db, current_user, request_id)
    )


@router.post("/{request_id}/decline", response_model=IncomingRequestOut)
async def decline(request_id: int, db: DbSession, current_user: CurrentUser) -> IncomingRequestOut:
    return IncomingRequestOut.build(
        await request_service.decline_request(db, current_user, request_id)
    )


@router.post("/{request_id}/cancel", response_model=MyRequestOut)
async def cancel(request_id: int, db: DbSession, current_user: CurrentUser) -> MyRequestOut:
    return MyRequestOut.build(await request_service.cancel_request(db, current_user, request_id))
