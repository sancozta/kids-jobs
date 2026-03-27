"""
Source Execution History Persistence Port
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from application.domain.entities.source_execution_history import SourceExecutionHistory


class SourceExecutionHistoryPersistencePort(ABC):

    @abstractmethod
    def save(self, execution: SourceExecutionHistory) -> SourceExecutionHistory:
        ...

    @abstractmethod
    def find_recent(
        self,
        *,
        executed_after: Optional[datetime] = None,
        limit: int = 5000,
    ) -> list[SourceExecutionHistory]:
        ...
