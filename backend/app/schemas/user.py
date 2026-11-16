from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas.common import UTCOutput


class UserCreate(BaseModel):
    """Request body for POST /auth/register."""

    email: EmailStr
    password: str = Field(min_length=8)
    display_name: str = Field(min_length=2, max_length=50)
    phone: str | None = Field(default=None, pattern=r"^\+?[0-9]{10,15}$")

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.lower()

    @field_validator("display_name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()

    @field_validator("password")
    @classmethod
    def fits_bcrypt(cls, v: str) -> str:
        # bcrypt only reads the first 72 *bytes* (emoji/accents use several bytes each).
        if len(v.encode()) > 72:
            raise ValueError("password must be at most 72 bytes")
        return v


class UserOut(BaseModel):
    """Your own profile. Note: no password field, ever."""

    # Lets Pydantic read values from an ORM object (user.id) instead of only from dicts.
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    display_name: str
    phone: str | None
    phone_verified: bool
    rating_avg: float | None
    rating_count: int
    is_admin: bool  # lets the app show the Admin screen; the API checks it again itself
    created_at: UTCOutput


class PersonOut(BaseModel):
    """How strangers see you: a name to look for, and signals that you can be trusted."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: str
    phone_verified: bool
    rating_avg: float | None
    rating_count: int


class ContactOut(PersonOut):
    """Only shown to people in the same accepted ride."""

    email: EmailStr
    phone: str | None
