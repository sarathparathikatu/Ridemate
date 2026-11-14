from pydantic import BaseModel


class Token(BaseModel):
    """Response body for POST /auth/login (shape required by the OAuth2 spec)."""

    access_token: str
    token_type: str = "bearer"
