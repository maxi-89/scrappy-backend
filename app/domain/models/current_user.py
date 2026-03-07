from dataclasses import dataclass


@dataclass(frozen=True)
class CurrentUser:
    sub: str  # Auth0 user ID, e.g. "auth0|64abc123"
    email: str  # User email address
