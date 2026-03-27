"""
Source - Domain Entity (Scraping Config)
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class Source:
    """Fonte de dados para scraping"""
    name: str                                    # "PORTAL_X"
    enabled: bool = True
    scraper_base_url: str = ""                   # "https://example.com"
    scraper_type: str = "http"                   # http | api | telegram
    scraper_schedule: str = "0 */2 * * *"        # Cron expression (fallback)
    extra_config: dict[str, Any] = field(default_factory=dict)  # Config persistida específica da source
    description: str = ""                        # Diagnóstico/consolidade recente
    last_extraction_status: Optional[str] = None  # SUCCESS | PARTIAL | ERROR
    last_extraction_http_status: Optional[int] = None
    last_extraction_message: Optional[str] = None
    last_extraction_at: Optional[datetime] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if not isinstance(self.extra_config, dict):
            self.extra_config = {}
