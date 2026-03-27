from datetime import datetime
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from adapters.inbound.http.source_controller import _compute_next_scheduled_at
from application.domain.entities.source import Source


def test_compute_next_scheduled_at_returns_next_cron_occurrence() -> None:
    source = Source(
        name="chaozao",
        enabled=True,
        scraper_schedule="0 */6 * * *",
    )

    next_run = _compute_next_scheduled_at(
        source,
        reference_time=datetime(2026, 3, 9, 15, 43, tzinfo=ZoneInfo("America/Sao_Paulo")),
    )

    assert next_run == "2026-03-09T18:00:00-03:00"


def test_compute_next_scheduled_at_returns_none_for_disabled_source() -> None:
    source = Source(
        name="chaozao",
        enabled=False,
        scraper_schedule="0 */6 * * *",
    )

    next_run = _compute_next_scheduled_at(
        source,
        reference_time=datetime(2026, 3, 9, 15, 43, tzinfo=ZoneInfo("America/Sao_Paulo")),
    )

    assert next_run is None


def test_compute_next_scheduled_at_returns_none_for_invalid_cron() -> None:
    source = Source(
        name="chaozao",
        enabled=True,
        scraper_schedule="cron-invalido",
    )

    next_run = _compute_next_scheduled_at(
        source,
        reference_time=datetime(2026, 3, 9, 15, 43, tzinfo=ZoneInfo("America/Sao_Paulo")),
    )

    assert next_run is None
