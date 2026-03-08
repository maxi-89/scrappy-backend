from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CreateOrderRequest(BaseModel):
    offer_id: str
    zone: str = Field(min_length=2, max_length=100)
    format: str = Field(pattern="^(csv|excel|json)$")


class CreateOrderResponse(BaseModel):
    order_id: str
    client_secret: str
    total_usd: float


class OrderResponse(BaseModel):
    id: str
    offer_id: str
    zone: str
    format: str
    status: str
    total_usd: float
    created_at: datetime
    paid_at: datetime | None
    completed_at: datetime | None


class ScrapingJobSchema(BaseModel):
    id: str
    category: str
    zone: str
    status: str
    records_scraped: int
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class OrderDetailResponse(OrderResponse):
    scraping_job: ScrapingJobSchema | None
