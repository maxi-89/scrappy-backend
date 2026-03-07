from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass
class Business:
    id: str
    scraping_job_id: str
    name: str
    category: str
    zone: str
    address: str | None
    phone: str | None
    website: str | None
    google_maps_url: str | None
    rating: Decimal | None
    review_count: int
    latitude: Decimal | None
    longitude: Decimal | None
    is_verified: bool
    scraped_at: datetime
    created_at: datetime

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("name is required")
        if not self.category.strip():
            raise ValueError("category is required")
        if not self.zone.strip():
            raise ValueError("zone is required")
        if not self.scraping_job_id.strip():
            raise ValueError("scraping_job_id is required")
        if self.rating is not None and not (Decimal("0.0") <= self.rating <= Decimal("5.0")):
            raise ValueError("rating must be between 0.0 and 5.0")
        if self.review_count < 0:
            raise ValueError("review_count must be >= 0")
