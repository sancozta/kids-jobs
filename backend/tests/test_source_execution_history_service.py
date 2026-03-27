from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from application.domain.entities.source_execution_history import SourceExecutionHistory
from application.domain.services.source_execution_history_service import SourceExecutionHistoryService


class _FakePersistence:
    def __init__(self) -> None:
        self.saved: list[SourceExecutionHistory] = []
        self.last_executed_after = None
        self.last_limit = None

    def save(self, execution: SourceExecutionHistory) -> SourceExecutionHistory:
        self.saved.append(execution)
        return execution

    def find_recent(self, *, executed_after=None, limit: int = 5000) -> list[SourceExecutionHistory]:
        self.last_executed_after = executed_after
        self.last_limit = limit
        return list(self.saved)


def test_list_recent_maps_period_to_expected_cutoff() -> None:
    persistence = _FakePersistence()
    service = SourceExecutionHistoryService(persistence=persistence)
    reference_time = datetime(2026, 3, 21, 12, 0, tzinfo=timezone.utc)

    service.list_recent(period="24h", limit=300, reference_time=reference_time)

    assert persistence.last_limit == 300
    assert persistence.last_executed_after == datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc)


def test_create_persists_execution_entry() -> None:
    persistence = _FakePersistence()
    service = SourceExecutionHistoryService(persistence=persistence)
    execution = SourceExecutionHistory(
        source_id=7,
        source_name="infojobs",
        trigger="scheduled",
        status="SUCCESS",
        success=True,
        scraped_count=15,
        published_count=15,
        duration_ms=2400,
        strategy="http_antibot",
        message="Extraído e publicado (15/15 itens)",
        executed_at=datetime(2026, 3, 21, 14, 30, tzinfo=timezone.utc),
    )

    created = service.create(execution)

    assert created is execution
    assert persistence.saved == [execution]
