"""
Source Execution History Controller
"""
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from adapters.outbound.persistence.source_execution_history_persistence_adapter import (
    SourceExecutionHistoryPersistenceAdapter,
)
from application.domain.services.source_execution_history_service import SourceExecutionHistoryService
from configuration.database_configuration import get_db

router = APIRouter(prefix="/api/v1/source-executions", tags=["Source Executions"])


class SourceExecutionHistoryResponse(BaseModel):
    id: int
    source_id: int
    source_name: str
    trigger: str
    status: str
    success: bool
    scraped_count: int
    published_count: int
    duration_ms: int
    strategy: str
    http_status_code: Optional[int] = None
    error_message: Optional[str] = None
    message: Optional[str] = None
    executed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


def _get_service(db: Session = Depends(get_db)) -> SourceExecutionHistoryService:
    return SourceExecutionHistoryService(
        persistence=SourceExecutionHistoryPersistenceAdapter(session=db),
    )


@router.get("", response_model=list[SourceExecutionHistoryResponse])
def list_source_executions(
    period: Literal["24h", "7d", "30d", "90d"] = Query("30d"),
    limit: int = Query(5000, ge=1, le=10000),
    service: SourceExecutionHistoryService = Depends(_get_service),
):
    executions = service.list_recent(period=period, limit=limit)
    return [SourceExecutionHistoryResponse.model_validate(execution.__dict__) for execution in executions]
