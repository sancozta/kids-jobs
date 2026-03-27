import requests

from application.domain.entities.rescrape_job import RescrapeJob
from application.domain.entities.scraped_item import ScrapedData, ScrapedItem
from application.domain.services.rescrape_job_service import (
    RescrapeEnqueueItem,
    RescrapeJobService,
)


class _FakePersistence:
    def __init__(self):
        self.jobs = []
        self._next_id = 1

    def save(self, job: RescrapeJob) -> RescrapeJob:
        saved = RescrapeJob(**job.__dict__)
        saved.id = self._next_id
        self._next_id += 1
        self.jobs.append(saved)
        return saved

    def update(self, job: RescrapeJob) -> RescrapeJob:
        for index, current in enumerate(self.jobs):
            if current.id == job.id:
                self.jobs[index] = RescrapeJob(**job.__dict__)
                return self.jobs[index]
        raise ValueError("job not found")

    def find_by_id(self, job_id: int):
        for job in self.jobs:
            if job.id == job_id:
                return job
        return None

    def find_active_by_source_url(self, source_name: str, url: str):
        normalized_source_name = source_name.strip().lower()
        for job in reversed(self.jobs):
            if job.source_name == normalized_source_name and job.url == url and job.status in {"queued", "processing"}:
                return job
        return None

    def find_pending(self, limit: int = 10):
        return [job for job in self.jobs if job.status == "queued"][:limit]

    def find_all(self, *, status=None, limit=100, offset=0):
        jobs = self.jobs
        if status:
            jobs = [job for job in jobs if job.status == status]
        return jobs[offset: offset + limit]


class _FakeSourceService:
    def __init__(self, source=None):
        self.source = source

    def get_by_name(self, source_name: str):
        return self.source


class _FakeScraper:
    def __init__(self, item: ScrapedItem | None, *, exc: Exception | None = None):
        self.item = item
        self.exc = exc
        self.last_fetch_diagnostics = None
        self.last_scrape_url_diagnostics = None

    def scrape_url(self, url: str):
        if self.exc is not None:
            raise self.exc
        return self.item

    def get_config(self):
        return None


class _TestableRescrapeJobService(RescrapeJobService):
    def __init__(self, *args, scraper=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._scraper = scraper

    def _resolve_scraper(self, source_name, source):
        return self._scraper


def test_enqueue_many_deduplicates_active_jobs() -> None:
    persistence = _FakePersistence()
    source_service = _FakeSourceService()
    published_job_ids = []
    service = RescrapeJobService(
        persistence=persistence,
        source_service=source_service,
        ingest_callable=lambda payload: None,
        publish_callable=lambda job_id: published_job_ids.append(job_id),
    )

    first = service.enqueue_many([RescrapeEnqueueItem(source_name="CHAOZAO", url="https://example.com/item/1")])
    second = service.enqueue_many([RescrapeEnqueueItem(source_name="chaozao", url="https://example.com/item/1")])

    assert first.queued_count == 1
    assert second.queued_count == 0
    assert second.deduplicated_count == 1
    assert len(persistence.jobs) == 1
    assert published_job_ids == [1]


def test_process_pending_marks_job_completed_and_calls_backend_ingest() -> None:
    persistence = _FakePersistence()
    source_service = _FakeSourceService()
    ingested_payloads = []
    item = ScrapedItem(
        url="https://example.com/item/1",
        source_name="chaozao",
        category_name="agribusiness",
        scraped_data=ScrapedData(title="Item limpo"),
    )
    service = _TestableRescrapeJobService(
        persistence=persistence,
        source_service=source_service,
        ingest_callable=lambda payload: ingested_payloads.append(payload),
        publish_callable=lambda job_id: None,
        scraper=_FakeScraper(item=item),
    )
    service.enqueue_many([RescrapeEnqueueItem(source_name="CHAOZAO", url="https://example.com/item/1", market_item_id=6)])

    summary = service.process_pending(limit=10)

    assert summary.processed_count == 1
    assert summary.completed_count == 1
    assert summary.error_count == 0
    assert ingested_payloads[0]["url"] == "https://example.com/item/1"
    assert persistence.jobs[0].status == "completed"
    assert persistence.jobs[0].attempts == 1


def test_process_pending_enqueues_market_delete_when_http_item_is_gone() -> None:
    persistence = _FakePersistence()
    source_service = _FakeSourceService()
    deleted_item_ids = []
    scraper = _FakeScraper(item=None)
    scraper.last_fetch_diagnostics = {
        "status_code": 404,
        "blocked": False,
        "error": "404 Client Error: Not Found",
    }
    service = _TestableRescrapeJobService(
        persistence=persistence,
        source_service=source_service,
        ingest_callable=lambda payload: None,
        delete_callable=lambda item_id: deleted_item_ids.append(item_id),
        publish_callable=lambda job_id: None,
        scraper=scraper,
    )
    service.enqueue_many([RescrapeEnqueueItem(source_name="VANHACK", url="https://example.com/item/404", market_item_id=9)])

    summary = service.process_pending(limit=10)

    assert summary.processed_count == 1
    assert summary.completed_count == 1
    assert summary.error_count == 0
    assert deleted_item_ids == [9]
    assert persistence.jobs[0].status == "completed"


def test_process_pending_enqueues_market_delete_when_http_scraper_raises_404() -> None:
    persistence = _FakePersistence()
    source_service = _FakeSourceService()
    deleted_item_ids = []
    response = requests.Response()
    response.status_code = 404
    response.url = "https://example.com/item/404"
    scraper = _FakeScraper(
        item=None,
        exc=requests.HTTPError("404 Client Error: Not Found", response=response),
    )
    service = _TestableRescrapeJobService(
        persistence=persistence,
        source_service=source_service,
        ingest_callable=lambda payload: None,
        delete_callable=lambda item_id: deleted_item_ids.append(item_id),
        publish_callable=lambda job_id: None,
        scraper=scraper,
    )
    service.enqueue_many([RescrapeEnqueueItem(source_name="VANHACK", url="https://example.com/item/404", market_item_id=11)])

    summary = service.process_pending(limit=10)

    assert summary.processed_count == 1
    assert summary.completed_count == 1
    assert summary.error_count == 0
    assert deleted_item_ids == [11]
    assert persistence.jobs[0].status == "completed"


def test_process_pending_enqueues_market_delete_when_telegram_message_is_missing() -> None:
    persistence = _FakePersistence()
    source_service = _FakeSourceService()
    deleted_item_ids = []
    scraper = _FakeScraper(item=None)
    scraper.last_scrape_url_diagnostics = {
        "missing": True,
        "reason": "Mensagem Telegram não encontrada",
        "url": "telegram://123/456",
    }
    service = _TestableRescrapeJobService(
        persistence=persistence,
        source_service=source_service,
        ingest_callable=lambda payload: None,
        delete_callable=lambda item_id: deleted_item_ids.append(item_id),
        publish_callable=lambda job_id: None,
        scraper=scraper,
    )
    service.enqueue_many([RescrapeEnqueueItem(source_name="TELEGRAM_JOBS_TI", url="telegram://123/456", market_item_id=7)])

    summary = service.process_pending(limit=10)

    assert summary.processed_count == 1
    assert summary.completed_count == 1
    assert summary.error_count == 0
    assert deleted_item_ids == [7]
    assert persistence.jobs[0].status == "completed"


def test_process_pending_keeps_error_when_scraper_fails_without_missing_signal() -> None:
    persistence = _FakePersistence()
    source_service = _FakeSourceService()
    scraper = _FakeScraper(item=None)
    scraper.last_fetch_diagnostics = {
        "status_code": None,
        "blocked": True,
        "error": "Blocked with status 403 for https://example.com/item/1",
    }
    service = _TestableRescrapeJobService(
        persistence=persistence,
        source_service=source_service,
        ingest_callable=lambda payload: None,
        delete_callable=lambda item_id: None,
        publish_callable=lambda job_id: None,
        scraper=scraper,
    )
    service.enqueue_many([RescrapeEnqueueItem(source_name="OLX_VEHICLES", url="https://example.com/item/1", market_item_id=5)])

    summary = service.process_pending(limit=10)

    assert summary.processed_count == 1
    assert summary.completed_count == 0
    assert summary.error_count == 1
    assert persistence.jobs[0].status == "error"


def test_process_pending_marks_job_error_when_scraper_is_unsupported() -> None:
    persistence = _FakePersistence()
    source_service = _FakeSourceService()
    service = _TestableRescrapeJobService(
        persistence=persistence,
        source_service=source_service,
        ingest_callable=lambda payload: None,
        publish_callable=lambda job_id: None,
        scraper=None,
    )
    service.enqueue_many([RescrapeEnqueueItem(source_name="CHAOZAO", url="https://example.com/item/1")])

    summary = service.process_pending(limit=10)

    assert summary.processed_count == 1
    assert summary.completed_count == 0
    assert summary.error_count == 1
    assert persistence.jobs[0].status == "error"
    assert "não encontrado" in (persistence.jobs[0].last_error or "")
