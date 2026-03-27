"""
Rescrape Job Service
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from typing import Callable, Optional

import requests

from adapters.outbound.scraping.scraper_loader import load_all_scrapers
from application.domain.entities.rescrape_job import RescrapeJob
from application.domain.entities.source import Source
from application.domain.services.scraper_execution_service import ScraperExecutionService
from application.domain.services.scraper_factory import ScraperFactory
from application.domain.services.scraper_registry import ScraperRegistry
from application.domain.services.source_service import SourceService
from application.ports.outbound.persistence.rescrape_job_persistence_port import RescrapeJobPersistencePort
from application.ports.outbound.scraping.scraper_port import ScraperPort

logger = logging.getLogger(__name__)


class DeleteQueuedForMissingItem(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass
class RescrapeEnqueueItem:
    source_name: str
    url: str
    market_item_id: Optional[int] = None


@dataclass
class RescrapeEnqueueSummary:
    queued_count: int
    deduplicated_count: int
    jobs: list[RescrapeJob]


@dataclass
class RescrapeProcessSummary:
    processed_count: int
    completed_count: int
    error_count: int
    jobs: list[RescrapeJob]


class RescrapeJobService:

    def __init__(
        self,
        persistence: RescrapeJobPersistencePort,
        source_service: SourceService,
        ingest_callable: Optional[Callable[[dict], None]] = None,
        delete_callable: Optional[Callable[[int], None]] = None,
        publish_callable: Optional[Callable[[int], None]] = None,
    ):
        self.persistence = persistence
        self.source_service = source_service
        self.ingest_callable = ingest_callable or self._ingest_to_backend
        self.delete_callable = delete_callable or self._enqueue_delete_in_backend
        self.publish_callable = publish_callable

    def enqueue_many(self, items: list[RescrapeEnqueueItem]) -> RescrapeEnqueueSummary:
        queued: list[RescrapeJob] = []
        deduplicated_count = 0

        for item in items:
            normalized_source_name = self._normalize_source_name(item.source_name)
            normalized_url = self._normalize_url(item.url)
            if not normalized_source_name or not normalized_url:
                continue

            existing = self.persistence.find_active_by_source_url(normalized_source_name, normalized_url)
            if existing:
                deduplicated_count += 1
                queued.append(existing)
                continue

            created = self.persistence.save(
                RescrapeJob(
                    source_name=normalized_source_name,
                    url=normalized_url,
                    market_item_id=item.market_item_id,
                    status="queued",
                )
            )
            self._publish_job(created)
            queued.append(created)

        return RescrapeEnqueueSummary(
            queued_count=len(queued) - deduplicated_count,
            deduplicated_count=deduplicated_count,
            jobs=queued,
        )

    def list_jobs(self, *, status: Optional[str] = None, limit: int = 100, offset: int = 0) -> list[RescrapeJob]:
        normalized_status = (status or "").strip().lower() or None
        return self.persistence.find_all(status=normalized_status, limit=limit, offset=offset)

    def process_pending(self, limit: int = 10) -> RescrapeProcessSummary:
        jobs = self.persistence.find_pending(limit=max(1, limit))
        processed_jobs: list[RescrapeJob] = []
        completed_count = 0
        error_count = 0

        for job in jobs:
            processing_job = self._mark_processing(job)
            try:
                scraped_item = self._scrape_job(processing_job)
                if scraped_item is None:
                    raise ValueError("Scraper não retornou item para a URL solicitada")

                self.ingest_callable(scraped_item.to_dict())
                completed_job = self._mark_completed(processing_job)
                processed_jobs.append(completed_job)
                completed_count += 1
            except DeleteQueuedForMissingItem as exc:
                self._delete_market_item_for_job(processing_job, exc.reason)
                completed_job = self._mark_completed(processing_job)
                processed_jobs.append(completed_job)
                completed_count += 1
            except Exception as exc:
                logger.error("Rescrape job %s failed: %s", processing_job.id, exc, exc_info=True)
                errored_job = self._mark_error(processing_job, str(exc))
                processed_jobs.append(errored_job)
                error_count += 1

        return RescrapeProcessSummary(
            processed_count=len(processed_jobs),
            completed_count=completed_count,
            error_count=error_count,
            jobs=processed_jobs,
        )

    def process_job_by_id(self, job_id: int) -> Optional[RescrapeJob]:
        job = self.persistence.find_by_id(job_id)
        if not job:
            return None
        if job.status != "queued":
            return None

        processing_job = self._mark_processing(job)
        try:
            scraped_item = self._scrape_job(processing_job)
            if scraped_item is None:
                raise ValueError("Scraper não retornou item para a URL solicitada")
            self.ingest_callable(scraped_item.to_dict())
            return self._mark_completed(processing_job)
        except DeleteQueuedForMissingItem as exc:
            self._delete_market_item_for_job(processing_job, exc.reason)
            return self._mark_completed(processing_job)
        except Exception as exc:
            logger.error("Rescrape job %s failed: %s", processing_job.id, exc, exc_info=True)
            return self._mark_error(processing_job, str(exc))

    def publish_pending(self, limit: int = 10) -> int:
        jobs = self.persistence.find_pending(limit=max(1, limit))
        published_count = 0
        for job in jobs:
            if self._publish_job(job):
                published_count += 1
        return published_count

    def _mark_processing(self, job: RescrapeJob) -> RescrapeJob:
        job.status = "processing"
        job.attempts = int(job.attempts or 0) + 1
        job.last_error = None
        return self.persistence.update(job)

    def _mark_completed(self, job: RescrapeJob) -> RescrapeJob:
        job.status = "completed"
        job.last_error = None
        job.last_processed_at = datetime.now(timezone.utc)
        return self.persistence.update(job)

    def _mark_error(self, job: RescrapeJob, error_message: str) -> RescrapeJob:
        job.status = "error"
        job.last_error = (error_message or "").strip()[:2000] or "Erro desconhecido"
        job.last_processed_at = datetime.now(timezone.utc)
        return self.persistence.update(job)

    def _scrape_job(self, job: RescrapeJob):
        source = self.source_service.get_by_name(job.source_name)
        scraper = self._resolve_scraper(job.source_name, source)
        if not scraper:
            raise ValueError(f"Scraper '{job.source_name}' não encontrado")

        try:
            item = scraper.scrape_url(job.url)
        except Exception as exc:
            if self._should_delete_missing_item(job=job, scraper=scraper, exc=exc):
                raise DeleteQueuedForMissingItem(self._build_missing_item_reason(job=job, scraper=scraper, exc=exc))
            raise

        if item is None and self._should_delete_missing_item(job=job, scraper=scraper):
            raise DeleteQueuedForMissingItem(self._build_missing_item_reason(job=job, scraper=scraper, exc=None))
        return item

    def _delete_market_item_for_job(self, job: RescrapeJob, reason: str) -> None:
        market_item_id = int(job.market_item_id or 0)
        if market_item_id <= 0:
            raise ValueError("Item ausente no site, mas o rescrape não possui market_item_id para exclusão")

        self.delete_callable(market_item_id)
        logger.info(
            "Rescrape job %s removeu market_item_id=%s: %s",
            job.id,
            market_item_id,
            reason,
        )

    @staticmethod
    def _error_indicates_missing(message: Optional[str]) -> bool:
        normalized = (message or "").strip().lower()
        if not normalized:
            return False
        return any(
            token in normalized
            for token in (
                "404",
                "410",
                "not found",
                "não encontrado",
                "nao encontrado",
                "não existe",
                "nao existe",
                "gone",
                "removed",
            )
        )

    def _should_delete_missing_item(self, *, job: RescrapeJob, scraper: ScraperPort, exc: Optional[Exception] = None) -> bool:
        if int(job.market_item_id or 0) <= 0:
            return False

        normalized_url = self._normalize_url(job.url)
        if normalized_url.startswith("telegram://"):
            diagnostics = getattr(scraper, "last_scrape_url_diagnostics", None)
            return isinstance(diagnostics, dict) and bool(diagnostics.get("missing"))

        fetch_diagnostics = getattr(scraper, "last_fetch_diagnostics", None)
        if isinstance(fetch_diagnostics, dict):
            status_code = fetch_diagnostics.get("status_code")
            blocked = bool(fetch_diagnostics.get("blocked"))
            error_message = str(fetch_diagnostics.get("error") or "")
            if status_code in {404, 410}:
                return True
            if not blocked and self._error_indicates_missing(error_message):
                return True

        if isinstance(exc, requests.HTTPError):
            response = getattr(exc, "response", None)
            if response is not None and getattr(response, "status_code", None) in {404, 410}:
                return True

        if exc and self._error_indicates_missing(str(exc)):
            return True

        return False

    def _build_missing_item_reason(self, *, job: RescrapeJob, scraper: ScraperPort, exc: Optional[Exception]) -> str:
        normalized_url = self._normalize_url(job.url)
        if normalized_url.startswith("telegram://"):
            diagnostics = getattr(scraper, "last_scrape_url_diagnostics", None)
            if isinstance(diagnostics, dict):
                reason = str(diagnostics.get("reason") or "").strip()
                if reason:
                    return reason

        fetch_diagnostics = getattr(scraper, "last_fetch_diagnostics", None)
        if isinstance(fetch_diagnostics, dict):
            status_code = fetch_diagnostics.get("status_code")
            if status_code in {404, 410}:
                return f"Item não está mais acessível no site (HTTP {status_code})"
            error_message = str(fetch_diagnostics.get("error") or "").strip()
            if error_message and self._error_indicates_missing(error_message):
                return error_message[:300]

        if exc:
            message = str(exc).strip()
            if message:
                return message[:300]
        return "Item não está mais acessível no site"

    def _publish_job(self, job: RescrapeJob) -> bool:
        if job.id is None or not self.publish_callable:
            return False
        try:
            self.publish_callable(job.id)
            if job.last_error:
                job.last_error = None
                self.persistence.update(job)
            return True
        except Exception as exc:
            logger.error("Falha ao agendar job de rescrape %s: %s", job.id, exc, exc_info=True)
            job.last_error = (str(exc) or "Falha ao agendar rescrape")[:2000]
            self.persistence.update(job)
            return False

    def _resolve_scraper(self, source_name: str, source: Optional[Source]) -> Optional[ScraperPort]:
        if not ScraperRegistry.get_all_scrapers():
            load_all_scrapers()

        scraper_name = self._normalize_source_name(source_name)
        scraper = ScraperFactory.create(scraper_name)
        if not scraper:
            return None

        config = scraper.get_config()
        if source and config:
            ScraperExecutionService.apply_source_overrides_to_config(config, source)
        return scraper

    @staticmethod
    def _normalize_source_name(source_name: Optional[str]) -> str:
        return (source_name or "").strip().lower()

    @staticmethod
    def _normalize_url(url: Optional[str]) -> str:
        normalized = (url or "").strip()
        return normalized.split("#", 1)[0] if normalized else ""

    @staticmethod
    def _ingest_to_backend(payload: dict) -> None:
        raise RuntimeError("RescrapeJobService requer ingest_callable explicito no kids-jobs")

    @staticmethod
    def _enqueue_delete_in_backend(market_item_id: int) -> None:
        raise RuntimeError("RescrapeJobService requer delete_callable explicito no kids-jobs")
