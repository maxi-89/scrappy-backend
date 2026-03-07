from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CreateScrapingJobRequest(BaseModel):
    category: str = Field(min_length=2, max_length=100)
    zone: str = Field(min_length=2, max_length=100)


class ScrapingJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
