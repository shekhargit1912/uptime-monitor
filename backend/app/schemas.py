"""Pydantic request/response schemas."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, HttpUrl


class MonitorCreate(BaseModel):
    # HttpUrl validates that the input is a real http(s) URL before we store it.
    url: HttpUrl
    name: str | None = None


class CheckOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status_code: int | None
    response_time_ms: float | None
    is_up: bool
    error: str | None
    checked_at: datetime


class MonitorOut(BaseModel):
    """A monitor plus its most recent check, which is what the dashboard renders."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    name: str | None
    created_at: datetime
    latest_check: CheckOut | None = None
