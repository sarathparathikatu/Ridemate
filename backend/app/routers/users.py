from fastapi import APIRouter

from app.dependencies.auth import CurrentUser
from app.models import User
from app.schemas.user import UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
async def read_me(current_user: CurrentUser) -> User:
    # No token logic here at all: get_current_user already ran and handed us the user.
    return current_user
