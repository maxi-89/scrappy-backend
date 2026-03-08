from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CreateOfferRequest(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    category: str = Field(min_length=2, max_length=100)
    description: str | None = None
    is_active: bool = False


class UpdateOfferRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    is_active: bool | None = None


class OfferResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    category: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PublicOfferResponse(BaseModel):
    id: str
    title: str
    category: str
    description: str | None
    is_active: bool
    price_usd: float | None = None
