from datetime import datetime, UTC
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from adapters.inbound.http.scraper_controller import _build_queued_response


def test_build_queued_response_maps_scheduler_payload() -> None:
    submitted_at = datetime(2026, 3, 17, 12, 0, tzinfo=UTC)

    response = _build_queued_response(
        {
            "job_id": "manual:source:12:abc123",
            "status": "queued",
            "queued_count": 1,
            "submitted_at": submitted_at,
        },
        source_id=12,
        source_name="fonte-a",
    )

    assert response.job_id == "manual:source:12:abc123"
    assert response.status == "queued"
    assert response.queued_count == 1
    assert response.submitted_at == submitted_at
    assert response.source_id == 12
    assert response.source_name == "fonte-a"
