"""Pydantic schemas for resume document API."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ResumeDocumentPayloadSchema(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)


class ResumeDocumentResponseSchema(BaseModel):
    key: str
    payload: dict[str, Any]
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True
