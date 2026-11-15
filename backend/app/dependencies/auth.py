from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import User

# Reads the "Authorization: Bearer <token>" header (401 if it's missing).
# tokenUrl tells Swagger's Authorize button where to log in.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    # One vague message for every failure: don't tell an attacker *why* a token failed.
    credentials_error = HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        user_id = decode_access_token(token)
    except (jwt.InvalidTokenError, ValueError):
        raise credentials_error from None

    # Token is genuine, but the account may have been deleted since it was issued.
    user = await db.get(User, user_id)
    if user is None:
        raise credentials_error
    return user


# Shorthand for endpoints:  async def endpoint(current_user: CurrentUser)
CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_verified_user(current_user: CurrentUser) -> User:
    """Like CurrentUser, but when REQUIRE_VERIFIED_PHONE is on the phone must be verified."""
    if get_settings().require_verified_phone and not current_user.phone_verified:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Verify your phone number first (Profile tab)")
    return current_user


# For actions that put you in a stranger's vehicle: posting and joining rides.
VerifiedUser = Annotated[User, Depends(get_verified_user)]
