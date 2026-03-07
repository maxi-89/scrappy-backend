from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

_VALID_STATUSES = {"pending", "running", "completed", "failed"}


@dataclass
class ScrapingJob:
    id: str
    category: str
    zone: str
    status: str
    order_id: str | None
    records_scraped: int
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime

    def __post_init__(self) -> None:
        if not self.category.strip():
            raise ValueError("category is required")
        if not self.zone.strip():
            raise ValueError("zone is required")
        if self.status not in _VALID_STATUSES:
            raise ValueError(f"status must be one of {_VALID_STATUSES}")
        if self.records_scraped < 0:
            raise ValueError("records_scraped must be >= 0")
