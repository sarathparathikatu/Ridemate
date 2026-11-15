from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from app.dependencies.db import DbSession
from app.models import User
from app.schemas.auth import RefreshRequest, Token
from app.schemas.user import UserCreate, UserOut
from app.services import token_service, user_service

router = APIRouter(prefix="/auth", tags=["auth"])


# response_model=UserOut acts as a filter: even though we return the full User object,
# only the public profile fields go out. hashed_password can never leak by accident.
@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(body: UserCreate, db: DbSession) -> User:
    try:
        return await user_service.create_user(db, body)
    except user_service.EmailAlreadyRegisteredError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered") from None


# OAuth2PasswordRequestForm reads form fields "username" + "password" (OAuth2 standard).
# We treat "username" as the email. Following the standard makes Swagger's
# "Authorize" button work out of the box.
@router.post("/login", response_model=Token)
async def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession) -> Token:
    user = await user_service.authenticate_user(db, form.username, form.password)
    if user is None:
        # Same message for "no such email" and "wrong password": don't reveal which emails exist.
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access, refresh = await token_service.issue_tokens(db, user.id)
    return Token(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=Token)
async def refresh(body: RefreshRequest, db: DbSession) -> Token:
    """Trade a refresh token for a new pair. The one you sent stops working."""
    access, refresh_token = await token_service.rotate(db, body.refresh_token)
    return Token(access_token=access, refresh_token=refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: RefreshRequest, db: DbSession) -> Response:
    # The access token still works until it expires (max 30 min): JWTs are stateless.
    await token_service.revoke(db, body.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
