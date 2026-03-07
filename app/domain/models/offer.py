from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Offer:
    id: str
    title: str
    category: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("title is required")
        if not self.category.strip():
            raise ValueError("category is required")
