"""
Rescrape Job - Domain Entity
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class RescrapeJob:
    """Fila persistente para reprocessamento de itens individuais."""

    source_name: str
    url: str
    status: str = "queued"
    market_item_id: Optional[int] = None
    attempts: int = 0
    last_error: Optional[str] = None
    last_processed_at: Optional[datetime] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
