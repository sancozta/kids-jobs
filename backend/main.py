"""Kids Jobs backend entrypoint."""
from __future__ import annotations

from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Callable, Optional
from uuid import uuid4

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from adapters.inbound.http.category_controller import router as category_router
from adapters.inbound.http.health_controller import router as health_router
from adapters.inbound.http.market_controller import router as market_router
from adapters.inbound.http.rescrape_controller import router as rescrape_router
from adapters.inbound.http.resume_document_controller import router as resume_document_router
from adapters.inbound.http.scraper_controller import router as scraper_router
from adapters.inbound.http.source_controller import router as source_router
from adapters.inbound.http.source_execution_history_controller import router as source_execution_history_router
from adapters.inbound.schedulers.apscheduler_adapter import APSchedulerAdapter
from adapters.outbound.persistence.category_persistence_adapter import CategoryPersistenceAdapter
from adapters.outbound.persistence.market_persistence_adapter import MarketPersistenceAdapter
from adapters.outbound.persistence.rescrape_job_persistence_adapter import RescrapeJobPersistenceAdapter
from adapters.outbound.persistence.source_execution_history_persistence_adapter import (
    SourceExecutionHistoryPersistenceAdapter,
)
from adapters.outbound.persistence.source_persistence_adapter import SourcePersistenceAdapter
from adapters.outbound.scraping.scraper_loader import load_all_scrapers
from application.domain.entities.source_execution_history import SourceExecutionHistory
from application.domain.exceptions.domain_exceptions import DomainException
from application.domain.services.category_service import CategoryService
from application.domain.services.market_service import MarketService
from application.domain.services.rescrape_job_service import RescrapeJobService, RescrapeProcessSummary
from application.domain.services.scraper_execution_service import (
    ScraperExecutionService,
    SourceExecutionResult,
)
from application.domain.services.scraper_metrics_service import ScraperMetricsService
from application.domain.services.scraper_registry import ScraperRegistry
from application.domain.services.source_execution_history_service import SourceExecutionHistoryService
from application.domain.services.source_service import SourceService
from configuration.database_configuration import SessionLocal, init_db
from configuration.logs_configuration import setup_logging
from configuration.settings_configuration import settings

setup_logging()

logger = logging.getLogger(__name__)
SWAGGER_FILE_PATH = Path(__file__).resolve().parent / "swagger.yml"

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Kids Jobs backend standalone para vagas, fontes e currículo.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(source_router)
app.include_router(source_execution_history_router)
app.include_router(category_router)
app.include_router(rescrape_router)
app.include_router(scraper_router)
app.include_router(market_router)
app.include_router(resume_document_router)

scheduler_adapter = APSchedulerAdapter()
scraper_metrics_service = ScraperMetricsService()
scraper_execution_service = ScraperExecutionService(metrics_service=scraper_metrics_service)

SCHEDULER_REFRESH_JOB_ID = "system:refresh_schedules"
SCHEDULER_RESCRAPE_JOB_ID = "system:process_rescrape_queue"
SCHEDULER_SCRAPER_JOB_PREFIX = "scraper:"
MANUAL_SOURCE_JOB_PREFIX = "manual:source:"
MANUAL_BATCH_JOB_PREFIX = "manual:batch:"
RESCRAPE_JOB_PREFIX = "rescrape:"

app.state.scraper_metrics_service = scraper_metrics_service
app.state.scraper_execution_service = scraper_execution_service


@app.exception_handler(DomainException)
def handle_domain_exception(_, exc: DomainException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.get("/swagger", include_in_schema=False)
def custom_swagger_ui():
    return HTMLResponse(
        """
        <!DOCTYPE html>
        <html lang="pt-BR">
          <head>
            <meta charset="UTF-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1.0" />
            <title>Kids Jobs Swagger</title>
            <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css" />
          </head>
          <body>
            <div id="swagger-ui"></div>
            <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
            <script>
              window.ui = SwaggerUIBundle({
                url: "/swagger.yml",
                dom_id: "#swagger-ui",
                deepLinking: true,
                presets: [SwaggerUIBundle.presets.apis],
                layout: "BaseLayout"
              });
            </script>
          </body>
        </html>
        """
    )


@app.get("/swagger.yml", include_in_schema=False)
def custom_swagger_yaml():
    return FileResponse(SWAGGER_FILE_PATH, media_type="application/yaml", filename="swagger.yml")


@app.get("/metrics")
def prometheus_metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


def _build_market_service(db) -> MarketService:
    return MarketService(
        repository=MarketPersistenceAdapter(session=db),
        source_service=SourceService(persistence=SourcePersistenceAdapter(session=db)),
        category_service=CategoryService(persistence=CategoryPersistenceAdapter(session=db)),
    )


def _build_rescrape_job_service(db, *, publish_callable: Optional[Callable[[int], None]] = None) -> RescrapeJobService:
    market_service = _build_market_service(db)
    return RescrapeJobService(
        persistence=RescrapeJobPersistenceAdapter(session=db),
        source_service=SourceService(persistence=SourcePersistenceAdapter(session=db)),
        ingest_callable=market_service.ingest_raw,
        delete_callable=market_service.delete,
        publish_callable=publish_callable,
    )


def _get_enabled_sources() -> list:
    db = SessionLocal()
    try:
        persistence = SourcePersistenceAdapter(session=db)
        source_service = SourceService(persistence=persistence)
        return source_service.get_all(enabled_only=True)
    finally:
        db.close()


def execute_source_job(source_id: int, trigger: str = "scheduled") -> Optional[dict]:
    db = SessionLocal()
    try:
        persistence = SourcePersistenceAdapter(session=db)
        source_service = SourceService(persistence=persistence)
        source = source_service.get_by_id(source_id)
        if not source:
            logger.warning("Source %s not found during execution", source_id)
            return None
        if not source.enabled:
            logger.info("Source %s (id=%s) está desabilitada", source.name, source.id)
            return None
    finally:
        db.close()

    result = scraper_execution_service.execute_source(source)
    extraction_summary = finalize_source_execution(source_id=source_id, result=result, trigger=trigger)

    if not result.success:
        logger.error(
            "Execução falhou para %s (id=%s): %s",
            source.name,
            source.id,
            result.error,
        )

    return {
        "source_id": result.source_id,
        "source_name": result.source_name,
        "success": result.success,
        "scraped_count": result.scraped_count,
        "published_count": result.published_count,
        "duration_ms": result.duration_ms,
        "strategy": result.strategy,
        "status": extraction_summary["status"],
        "http_status_code": result.http_status_code,
        "error": result.error,
    }


def execute_all_enabled_sources_job(trigger: str = "manual") -> dict:
    results = []
    for source in _get_enabled_sources():
        result = execute_source_job(source.id, trigger=trigger)
        if result:
            results.append(result)

    summary = {
        "total_requested": len(results),
        "total_succeeded": sum(1 for result in results if result.get("success")),
        "total_failed": sum(1 for result in results if not result.get("success")),
    }
    logger.info("Execução manual em lote finalizada: %s", summary)
    return summary


def enqueue_manual_source_run(source_id: int) -> dict:
    submitted_at = datetime.now(timezone.utc)
    job_id = f"{MANUAL_SOURCE_JOB_PREFIX}{source_id}:{uuid4().hex}"
    scheduler_adapter.add_one_off_job(
        func=execute_source_job,
        job_id=job_id,
        name=f"manual:source:{source_id}",
        run_at=submitted_at,
        args=[source_id, "manual"],
    )
    return {
        "job_id": job_id,
        "status": "queued",
        "queued_count": 1,
        "submitted_at": submitted_at,
    }


def enqueue_manual_run_all(queued_count: int) -> dict:
    submitted_at = datetime.now(timezone.utc)
    job_id = f"{MANUAL_BATCH_JOB_PREFIX}{uuid4().hex}"
    scheduler_adapter.add_one_off_job(
        func=execute_all_enabled_sources_job,
        job_id=job_id,
        name="manual:run-all",
        run_at=submitted_at,
        args=["manual"],
    )
    return {
        "job_id": job_id,
        "status": "queued",
        "queued_count": queued_count,
        "submitted_at": submitted_at,
    }


def finalize_source_execution(source_id: int, result: SourceExecutionResult, trigger: str) -> dict:
    status = scraper_execution_service.classify_extraction_status(result)
    message = scraper_execution_service.build_extraction_message(result)
    source_name = result.source_name
    executed_at = datetime.now(timezone.utc)

    db = SessionLocal()
    try:
        source_persistence = SourcePersistenceAdapter(session=db)
        source_service = SourceService(persistence=source_persistence)
        history_service = SourceExecutionHistoryService(
            persistence=SourceExecutionHistoryPersistenceAdapter(session=db),
        )
        latest_source = source_service.get_by_id(source_id)
        if latest_source:
            latest_source.last_extraction_status = status
            latest_source.last_extraction_http_status = result.http_status_code
            latest_source.last_extraction_message = message
            latest_source.last_extraction_at = executed_at
            source_service.update(latest_source)
            source_name = latest_source.name

        history_service.create(
            SourceExecutionHistory(
                source_id=source_id,
                source_name=source_name,
                trigger=(trigger or "scheduled").strip().lower(),
                status=status,
                success=result.success,
                scraped_count=result.scraped_count,
                published_count=result.published_count,
                duration_ms=result.duration_ms,
                strategy=result.strategy,
                http_status_code=result.http_status_code,
                error_message=result.error,
                message=message,
                executed_at=executed_at,
            )
        )
    finally:
        db.close()

    return {
        "status": status,
        "message": message,
        "source_name": source_name,
    }


def load_dynamic_schedules():
    logger.info("Carregando schedules do banco...")
    try:
        sources = _get_enabled_sources()
        scheduler_adapter.remove_jobs_by_prefix(SCHEDULER_SCRAPER_JOB_PREFIX)
        scheduled_count = 0

        for source in sources:
            scraper_name = source.name.strip().lower()
            cron_expression = source.scraper_schedule

            if not scraper_name or not ScraperRegistry.get_scraper_class(scraper_name):
                logger.warning("Scraper '%s' não encontrado no registry", scraper_name)
                continue

            try:
                scheduler_adapter.add_job(
                    func=execute_source_job,
                    cron_expression=cron_expression,
                    args=[source.id, "scheduled"],
                    job_id=f"{SCHEDULER_SCRAPER_JOB_PREFIX}{source.id}",
                    name=f"scraper:{scraper_name}",
                )
                scheduled_count += 1
            except ValueError as exc:
                logger.error(
                    "Schedule inválido '%s' para source '%s' (id=%s): %s",
                    cron_expression,
                    source.name,
                    source.id,
                    exc,
                )

        logger.info("Schedules dinâmicos carregados: %s ativos", scheduled_count)
    except Exception as exc:
        logger.error("Erro ao carregar schedules: %s", exc, exc_info=True)


def process_rescrape_job(job_id: int):
    db = SessionLocal()
    try:
        service = _build_rescrape_job_service(db)
        result = service.process_job_by_id(job_id)
        if result:
            logger.info("Rescrape job %s processado com status=%s", job_id, result.status)
        return result
    finally:
        db.close()


def publish_rescrape_job(job_id: int) -> None:
    run_at = datetime.now(timezone.utc)
    scheduler_adapter.add_one_off_job(
        func=process_rescrape_job,
        job_id=f"{RESCRAPE_JOB_PREFIX}{job_id}:{uuid4().hex}",
        name=f"rescrape:{job_id}",
        run_at=run_at,
        args=[job_id],
    )


def process_pending_rescrape_jobs(limit: int = 10) -> RescrapeProcessSummary:
    db = SessionLocal()
    try:
        service = _build_rescrape_job_service(db, publish_callable=publish_rescrape_job)
        result = service.process_pending(limit=limit)
        if result.processed_count > 0:
            logger.info(
                "Processamento de rescrape concluído: processed=%s completed=%s errors=%s",
                result.processed_count,
                result.completed_count,
                result.error_count,
            )
        return result
    finally:
        db.close()


@app.on_event("startup")
def on_startup():
    init_db()

    if settings.scraping_seed_on_startup:
        try:
            from scripts.seed_sources import seed_sources

            seed_summary = seed_sources()
            logger.info("Resumo do seed de fontes: %s", seed_summary)
        except Exception as exc:
            logger.error("Erro ao executar seed de fontes: %s", exc, exc_info=True)

    if not ScraperRegistry.get_all_scrapers():
        load_all_scrapers()

    load_dynamic_schedules()

    scheduler_adapter.scheduler.add_job(
        func=load_dynamic_schedules,
        trigger="interval",
        minutes=5,
        id=SCHEDULER_REFRESH_JOB_ID,
        name="Refresh Schedules from DB",
        replace_existing=True,
    )
    scheduler_adapter.scheduler.add_job(
        func=process_pending_rescrape_jobs,
        trigger="interval",
        seconds=settings.rescrape_queue_schedule_seconds,
        id=SCHEDULER_RESCRAPE_JOB_ID,
        name="Process Rescrape Queue",
        replace_existing=True,
    )

    scheduler_adapter.start()
    app.state.finalize_source_execution = finalize_source_execution
    app.state.publish_rescrape_job = publish_rescrape_job
    app.state.process_pending_rescrape_jobs = process_pending_rescrape_jobs
    app.state.enqueue_manual_source_run = enqueue_manual_source_run
    app.state.enqueue_manual_run_all = enqueue_manual_run_all


@app.on_event("shutdown")
def on_shutdown():
    logger.info("Encerrando kids-jobs backend...")
    scheduler_adapter.shutdown()


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=settings.port, reload=settings.debug)
