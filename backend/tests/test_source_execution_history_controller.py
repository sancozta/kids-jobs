from datetime import datetime, timezone
from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from adapters.inbound.http.source_execution_history_controller import (
    _get_service,
    router,
)
from application.domain.entities.source_execution_history import SourceExecutionHistory


class _FakeService:
    def __init__(self) -> None:
        self.last_period = None
        self.last_limit = None

    def list_recent(self, *, period="30d", limit=5000):
        self.last_period = period
        self.last_limit = limit
        return [
            SourceExecutionHistory(
                id=11,
                source_id=3,
                source_name="zapimoveis",
                trigger="manual",
                status="PARTIAL",
                success=True,
                scraped_count=18,
                published_count=11,
                duration_ms=3200,
                strategy="browser_playwright",
                http_status_code=200,
                message="Extração/publicação parcial (11/18 itens)",
                executed_at=datetime(2026, 3, 21, 11, 45, tzinfo=timezone.utc),
            )
        ]


def test_list_source_executions_returns_history_for_requested_period() -> None:
    app = FastAPI()
    app.include_router(router)
    service = _FakeService()
    app.dependency_overrides[_get_service] = lambda: service
    client = TestClient(app)

    response = client.get("/api/v1/source-executions", params={"period": "7d", "limit": 200})

    assert response.status_code == 200
    assert service.last_period == "7d"
    assert service.last_limit == 200
    assert response.json() == [
        {
            "id": 11,
            "source_id": 3,
            "source_name": "zapimoveis",
            "trigger": "manual",
            "status": "PARTIAL",
            "success": True,
            "scraped_count": 18,
            "published_count": 11,
            "duration_ms": 3200,
            "strategy": "browser_playwright",
            "http_status_code": 200,
            "error_message": None,
            "message": "Extração/publicação parcial (11/18 itens)",
            "executed_at": "2026-03-21T11:45:00Z",
            "created_at": None,
        }
    ]
