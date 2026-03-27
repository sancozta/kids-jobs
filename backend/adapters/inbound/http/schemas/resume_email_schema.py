"""Schemas for resume email sending."""
from typing import Any
from typing import Literal

from pydantic import BaseModel, Field


class ResumeEmailSendSchema(BaseModel):
    to_email: str = Field(..., min_length=3, max_length=255)
    subject: str = Field(..., min_length=1, max_length=255)
    message: str = Field(default="")
    sender_profile: Literal["company", "personal"] = Field(default="personal")
    reply_to_email: str = Field(default="", max_length=255)
    resume_payload: dict[str, Any] = Field(...)
    filename: str = Field(default="curriculo.pdf", min_length=1, max_length=255)
    locale: Literal["pt", "en"] = Field(default="pt")


class ResumeEmailSendResponseSchema(BaseModel):
    status: str
    email_id: str
