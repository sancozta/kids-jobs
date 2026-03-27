"""
Category - Domain Entity (Scraping Config)
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Category:
    """Categoria de scraping vinculada a uma source, com hierarquia via category_id"""
    name: str                                    # "Imoveis"
    source_id: int
    scrape_path: Optional[str] = None            # "/imoveis/apartamentos"
    category_id: Optional[int] = None            # Parent category (hierarquia)
    schedule: Optional[str] = None               # Override do source schedule
    enabled: bool = True
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
