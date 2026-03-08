from __future__ import annotations

from pydantic import BaseModel, Field


class PricingEntryResponse(BaseModel):
    id: str
    zone: str
    price_usd: float


class UpsertPricingEntry(BaseModel):
    zone: str = Field(min_length=2, max_length=100)
    price_usd: float = Field(ge=0)


class UpsertPricingRequest(BaseModel):
    entries: list[UpsertPricingEntry] = Field(min_length=1)
