"""
Source Execution History Persistence Adapter - SQLite implementation
"""
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from adapters.outbound.persistence.models.source_execution_history_model import SourceExecutionHistoryModel
from application.domain.entities.source_execution_history import SourceExecutionHistory
from application.ports.outbound.persistence.source_execution_history_persistence_port import (
    SourceExecutionHistoryPersistencePort,
)


class SourceExecutionHistoryPersistenceAdapter(SourceExecutionHistoryPersistencePort):

    def __init__(self, session: Session):
        self.session = session

    def save(self, execution: SourceExecutionHistory) -> SourceExecutionHistory:
        model = SourceExecutionHistoryModel.from_entity(execution)
        self.session.add(model)
        self.session.commit()
        self.session.refresh(model)
        return model.to_entity()

    def find_recent(
        self,
        *,
        executed_after: Optional[datetime] = None,
        limit: int = 5000,
    ) -> list[SourceExecutionHistory]:
        query = self.session.query(SourceExecutionHistoryModel)
        if executed_after is not None:
            query = query.filter(SourceExecutionHistoryModel.executed_at >= executed_after)

        models = (
            query.order_by(
                SourceExecutionHistoryModel.executed_at.desc(),
                SourceExecutionHistoryModel.id.desc(),
            )
            .limit(limit)
            .all()
        )
        return [model.to_entity() for model in models]
