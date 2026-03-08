from dataclasses import dataclass, field


@dataclass(frozen=True)
class CurrentUser:
    sub: str  # Auth0 user ID, e.g. "auth0|64abc123"
    email: str  # User email address
    user_id: str = field(default="")  # Local DB user UUID — populated after sync
