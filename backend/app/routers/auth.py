from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.db.session import get_db
from app.models import User
from app.schemas.auth import Token
from app.schemas.user import UserCreate, UserOut
from app.services import user_service

router = APIRouter(prefix="/auth", tags=["auth"])


# response_model=UserOut acts as a filter: even though we return the full User object,
# only id/email/created_at go out. hashed_password can never leak by accident.
@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(body: UserCreate, db: Annotated[AsyncSession, Depends(get_db)]) -> User:
    try:
        return await user_service.create_user(db, body)
    except user_service.EmailAlreadyRegisteredError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered") from None


# OAuth2PasswordRequestForm reads form fields "username" + "password" (OAuth2 standard).
# We treat "username" as the email. Following the standard makes Swagger's
# "Authorize" button work out of the box (used in the next stage).
@router.post("/login", response_model=Token)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Token:
    user = await user_service.authenticate_user(db, form.username, form.password)
    if user is None:
        # Same message for "no such email" and "wrong password": don't reveal which emails exist.
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(access_token=create_access_token(user.id))
