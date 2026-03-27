"""
Source Execution History - Domain Entity
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class SourceExecutionHistory:
    source_id: int
    source_name: str
    trigger: str
    status: str
    success: bool
    scraped_count: int
    published_count: int
    duration_ms: int
    strategy: str
    executed_at: datetime
    http_status_code: Optional[int] = None
    error_message: Optional[str] = None
    message: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
