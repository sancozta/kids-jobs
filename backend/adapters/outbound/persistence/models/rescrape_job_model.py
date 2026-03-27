"""
Rescrape Job Model - SQLAlchemy Model for SQLite
"""
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text

from application.domain.entities.rescrape_job import RescrapeJob
from configuration.database_configuration import Base


class RescrapeJobModel(Base):
    __tablename__ = "sc_rescrape_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_name = Column(String, nullable=False, index=True)
    url = Column(Text, nullable=False, index=True)
    status = Column(String, nullable=False, default="queued", index=True)
    market_item_id = Column(Integer, nullable=True, index=True)
    attempts = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)
    last_processed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def to_entity(self) -> RescrapeJob:
        return RescrapeJob(
            id=self.id,
            source_name=self.source_name,
            url=self.url,
            status=self.status,
            market_item_id=self.market_item_id,
            attempts=self.attempts,
            last_error=self.last_error,
            last_processed_at=self.last_processed_at,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @staticmethod
    def from_entity(entity: RescrapeJob) -> "RescrapeJobModel":
        return RescrapeJobModel(
            id=entity.id,
            source_name=entity.source_name,
            url=entity.url,
            status=entity.status,
            market_item_id=entity.market_item_id,
            attempts=entity.attempts,
            last_error=entity.last_error,
            last_processed_at=entity.last_processed_at,
        )
