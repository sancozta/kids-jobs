"""Resume document domain entity."""
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional


@dataclass
class ResumeDocument:
    key: str
    payload: dict[str, Any]
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
