from fastapi import APIRouter

from app.dependencies.auth import CurrentUser
from app.dependencies.db import DbSession
from app.schemas.join_request import IncomingRequestOut, MyRequestOut
from app.services import request_service

router = APIRouter(prefix="/requests", tags=["requests"])


@router.get("/mine", response_model=list[MyRequestOut])
async def my_requests(db: DbSession, current_user: CurrentUser) -> list[MyRequestOut]:
    return [MyRequestOut.build(r) for r in await request_service.list_my_requests(db, current_user)]


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
