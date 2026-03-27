"""
Source Model - SQLAlchemy Model for SQLite
"""
import json
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from configuration.database_configuration import Base
from application.domain.entities.source import Source


class SourceModel(Base):
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False, index=True)
    enabled = Column(Boolean, default=True, nullable=False)
    scraper_base_url = Column(String, nullable=True, default="")
    scraper_type = Column(String, nullable=False, default="http")
    scraper_schedule = Column(String, nullable=False, default="0 */2 * * *")
    extra_config = Column(Text, nullable=False, default="{}")
    description = Column(Text, nullable=False, default="")
    last_extraction_status = Column(String, nullable=True)
    last_extraction_http_status = Column(Integer, nullable=True)
    last_extraction_message = Column(Text, nullable=True)
    last_extraction_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def to_entity(self) -> Source:
        try:
            parsed_extra_config = json.loads(self.extra_config) if self.extra_config else {}
        except (TypeError, ValueError, json.JSONDecodeError):
            parsed_extra_config = {}
        if not isinstance(parsed_extra_config, dict):
            parsed_extra_config = {}

        return Source(
            id=self.id,
            name=self.name,
            enabled=self.enabled,
            scraper_base_url=self.scraper_base_url or "",
            scraper_type=self.scraper_type,
            scraper_schedule=self.scraper_schedule,
            extra_config=parsed_extra_config,
            description=self.description or "",
            last_extraction_status=self.last_extraction_status,
            last_extraction_http_status=self.last_extraction_http_status,
            last_extraction_message=self.last_extraction_message,
            last_extraction_at=self.last_extraction_at,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @staticmethod
    def from_entity(entity: Source) -> "SourceModel":
        return SourceModel(
            id=entity.id,
            name=entity.name,
            enabled=entity.enabled,
            scraper_base_url=entity.scraper_base_url,
            scraper_type=entity.scraper_type,
            scraper_schedule=entity.scraper_schedule,
            extra_config=json.dumps(entity.extra_config or {}, ensure_ascii=True, sort_keys=True),
            description=entity.description,
            last_extraction_status=entity.last_extraction_status,
            last_extraction_http_status=entity.last_extraction_http_status,
            last_extraction_message=entity.last_extraction_message,
            last_extraction_at=entity.last_extraction_at,
        )
