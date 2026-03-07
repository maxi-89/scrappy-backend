from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class User:
    id: str
    auth0_sub: str
    email: str
    full_name: str | None
    created_at: datetime

    def __post_init__(self) -> None:
        if not self.auth0_sub:
            raise ValueError("auth0_sub is required")
        if not self.email or "@" not in self.email:
            raise ValueError("email is required and must be valid")
