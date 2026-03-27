"""
Source Execution History Service
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from application.domain.entities.source_execution_history import SourceExecutionHistory
from application.ports.outbound.persistence.source_execution_history_persistence_port import (
    SourceExecutionHistoryPersistencePort,
)

ExecutionHistoryPeriod = Literal["24h", "7d", "30d", "90d"]


class SourceExecutionHistoryService:
    PERIOD_TO_DELTA = {
        "24h": timedelta(hours=24),
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
        "90d": timedelta(days=90),
    }

    def __init__(self, persistence: SourceExecutionHistoryPersistencePort):
        self.persistence = persistence

    def create(self, execution: SourceExecutionHistory) -> SourceExecutionHistory:
        return self.persistence.save(execution)

    def list_recent(
        self,
        *,
        period: ExecutionHistoryPeriod = "30d",
        limit: int = 5000,
        reference_time: Optional[datetime] = None,
    ) -> list[SourceExecutionHistory]:
        executed_after = self.resolve_executed_after(period=period, reference_time=reference_time)
        return self.persistence.find_recent(executed_after=executed_after, limit=limit)

    @classmethod
    def resolve_executed_after(
        cls,
        *,
        period: ExecutionHistoryPeriod,
        reference_time: Optional[datetime] = None,
    ) -> datetime:
        delta = cls.PERIOD_TO_DELTA.get(period, cls.PERIOD_TO_DELTA["30d"])
        now = reference_time or datetime.now(timezone.utc)
        return now - delta
