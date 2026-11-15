from pydantic import BaseModel


class Token(BaseModel):
    """Response body for login and refresh (access_token/token_type follow the OAuth2 spec)."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str
