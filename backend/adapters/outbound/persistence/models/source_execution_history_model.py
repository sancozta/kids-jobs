"""
Source Execution History Model - SQLAlchemy model for SQLite
"""
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from application.domain.entities.source_execution_history import SourceExecutionHistory
from configuration.database_configuration import Base


class SourceExecutionHistoryModel(Base):
    __tablename__ = "source_execution_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(Integer, nullable=False, index=True)
    source_name = Column(String, nullable=False, index=True)
    trigger = Column(String, nullable=False, default="scheduled")
    status = Column(String, nullable=False)
    success = Column(Boolean, nullable=False, default=False)
    scraped_count = Column(Integer, nullable=False, default=0)
    published_count = Column(Integer, nullable=False, default=0)
    duration_ms = Column(Integer, nullable=False, default=0)
    strategy = Column(String, nullable=False, default="http_basic")
    http_status_code = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    message = Column(Text, nullable=True)
    executed_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def to_entity(self) -> SourceExecutionHistory:
        return SourceExecutionHistory(
            id=self.id,
            source_id=self.source_id,
            source_name=self.source_name,
            trigger=self.trigger,
            status=self.status,
            success=bool(self.success),
            scraped_count=int(self.scraped_count or 0),
            published_count=int(self.published_count or 0),
            duration_ms=int(self.duration_ms or 0),
            strategy=self.strategy or "",
            http_status_code=self.http_status_code,
            error_message=self.error_message,
            message=self.message,
            executed_at=self.executed_at,
            created_at=self.created_at,
        )

    @staticmethod
    def from_entity(entity: SourceExecutionHistory) -> "SourceExecutionHistoryModel":
        return SourceExecutionHistoryModel(
            id=entity.id,
            source_id=entity.source_id,
            source_name=entity.source_name,
            trigger=entity.trigger,
            status=entity.status,
            success=entity.success,
            scraped_count=entity.scraped_count,
            published_count=entity.published_count,
            duration_ms=entity.duration_ms,
            strategy=entity.strategy,
            http_status_code=entity.http_status_code,
            error_message=entity.error_message,
            message=entity.message,
            executed_at=entity.executed_at,
            created_at=entity.created_at,
        )
