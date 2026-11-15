from fastapi import APIRouter, Depends, Response, status

from app.dependencies.auth import CurrentUser
from app.dependencies.db import DbSession
from app.dependencies.rate_limit import per_user
from app.models import User
from app.schemas.safety import BlockedUserOut, OtpSent, PhoneOtpRequest, PhoneVerifyRequest, ReportCreate
from app.schemas.user import UserOut
from app.services import phone_service, safety_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
async def read_me(current_user: CurrentUser) -> User:
    # No token logic here at all: get_current_user already ran and handed us the user.
    return current_user


# 3 codes per 10 minutes: each text costs money, and this stops "SMS bombing" a number.
@router.post(
    "/me/phone/send-code",
    response_model=OtpSent,
    dependencies=[Depends(per_user("otp-send", limit=3, window_seconds=600))],
)
async def send_phone_code(body: PhoneOtpRequest, current_user: CurrentUser) -> OtpSent:
    dev_code = await phone_service.send_code(current_user, body.phone)
    return OtpSent(expires_in_seconds=phone_service.OTP_TTL_SECONDS, dev_code=dev_code)


@router.post(
    "/me/phone/verify",
    response_model=UserOut,
    dependencies=[Depends(per_user("otp-verify", limit=10, window_seconds=600))],
)
async def verify_phone(body: PhoneVerifyRequest, db: DbSession, current_user: CurrentUser) -> User:
    return await phone_service.verify_code(db, current_user, body.code)


@router.get("/me/blocks", response_model=list[BlockedUserOut])
async def my_blocks(db: DbSession, current_user: CurrentUser) -> list[BlockedUserOut]:
    return await safety_service.list_blocked(db, current_user)


@router.post("/{user_id}/block", status_code=status.HTTP_204_NO_CONTENT)
async def block_user(user_id: int, db: DbSession, current_user: CurrentUser) -> Response:
    await safety_service.block(db, current_user, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{user_id}/block", status_code=status.HTTP_204_NO_CONTENT)
async def unblock_user(user_id: int, db: DbSession, current_user: CurrentUser) -> Response:
    await safety_service.unblock(db, current_user, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{user_id}/report",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(per_user("report", limit=10, window_seconds=3600))],
)
async def report_user(
    user_id: int, body: ReportCreate, db: DbSession, current_user: CurrentUser
) -> dict[str, str]:
    await safety_service.report(db, current_user, user_id, body)
    return {"status": "received"}
