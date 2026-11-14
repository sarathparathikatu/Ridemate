from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
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
    settings = get_settings()
    try:
        # Checks the signature AND expiry. algorithms is an explicit allow-list, so a
        # token claiming a different algorithm (e.g. "none") is rejected.
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "exp"]},
        )
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, ValueError):
        raise credentials_error from None

    # Token is genuine, but the account may have been deleted since it was issued.
    user = await db.get(User, user_id)
    if user is None:
        raise credentials_error
    return user


# Shorthand for endpoints:  async def endpoint(current_user: CurrentUser)
CurrentUser = Annotated[User, Depends(get_current_user)]
