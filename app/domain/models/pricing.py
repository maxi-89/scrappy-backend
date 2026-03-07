from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass
class Pricing:
    id: str
    zone: str
    price_usd: Decimal
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if not self.zone.strip():
            raise ValueError("zone is required")
        if self.price_usd < Decimal("0"):
            raise ValueError("price_usd must be >= 0")
