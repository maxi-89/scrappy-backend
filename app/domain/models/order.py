from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

_VALID_FORMATS = {"csv", "excel", "json"}
_VALID_STATUSES = {"pending", "paid", "scraping", "completed", "failed", "refunded"}


@dataclass
class Order:
    id: str
    user_id: str
    offer_id: str
    zone: str
    format: str
    status: str
    total_usd: Decimal
    stripe_payment_intent_id: str | None
    scraping_job_id: str | None
    result_path: str | None
    created_at: datetime
    paid_at: datetime | None
    completed_at: datetime | None

    def __post_init__(self) -> None:
        if not self.zone.strip():
            raise ValueError("zone is required")
        if self.format not in _VALID_FORMATS:
            raise ValueError(f"format must be one of {_VALID_FORMATS}")
        if self.status not in _VALID_STATUSES:
            raise ValueError(f"status must be one of {_VALID_STATUSES}")
        if self.total_usd < Decimal("0"):
            raise ValueError("total_usd must be >= 0")
