"""
Notification Dispatch Service
Sends scraping execution events to hunt-backend notifications API.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import requests

from application.domain.services.scraper_execution_service import SourceExecutionResult
from configuration.settings_configuration import settings

logger = logging.getLogger(__name__)


class NotificationDispatchService:
    """Dispatches notifications to hunt-backend when extraction runs complete."""

    @staticmethod
    def _status_to_type(status: str) -> str:
        if status == "SUCCESS":
            return "success"
        if status == "PARTIAL":
            return "warning"
        return "error"

    @staticmethod
    def _status_to_label(status: str) -> str:
        if status == "SUCCESS":
            return "Extraído com Dados"
        if status == "PARTIAL":
            return "Extraído Sem Dados"
        return "Erro"

    def _build_payload(
        self,
        *,
        source_id: int,
        source_name: str,
        status: str,
        result: SourceExecutionResult,
        trigger: str,
    ) -> dict:
        timestamp = datetime.now(timezone.utc).isoformat()
        status_label = self._status_to_label(status)
        details = [
            f"Status: {status_label} ({status})",
            f"Origem: {source_name}",
            f"Execução: {trigger}",
            f"Itens extraídos: {result.scraped_count}",
            f"Itens publicados: {result.published_count}",
            f"Duração: {result.duration_ms}ms",
        ]

        if result.http_status_code is not None:
            details.append(f"HTTP: {result.http_status_code}")

        if result.error:
            details.append(f"Erro: {result.error}")

        return {
            "title": f"Scraping executado: {source_name}",
            "message": " | ".join(details),
            "type": self._status_to_type(status),
            "payload": {
                "source_id": source_id,
                "source_name": source_name,
                "status": status,
                "trigger": trigger,
                "http_status_code": result.http_status_code,
                "scraped_count": result.scraped_count,
                "published_count": result.published_count,
                "duration_ms": result.duration_ms,
                "strategy": result.strategy,
                "error": result.error,
                "executed_at": timestamp,
            },
        }

    def notify_scraping_execution(
        self,
        *,
        source_id: int,
        source_name: str,
        status: str,
        result: SourceExecutionResult,
        trigger: str,
    ) -> None:
        base_url = (settings.backend_api_url or "").strip().rstrip("/")
        if not base_url:
            logger.debug("BACKEND_API_URL not configured; notification dispatch skipped")
            return

        path = (settings.backend_notifications_path or "").strip() or "/api/v1/notifications/"
        if not path.startswith("/"):
            path = f"/{path}"
        endpoint = f"{base_url}{path}"
        payload = self._build_payload(
            source_id=source_id,
            source_name=source_name,
            status=status,
            result=result,
            trigger=trigger,
        )

        try:
            response = requests.post(
                endpoint,
                json=payload,
                timeout=settings.backend_request_timeout_seconds,
            )
            if response.status_code >= 400:
                logger.warning(
                    "Notification dispatch failed (%s): %s",
                    response.status_code,
                    response.text[:500],
                )
        except Exception as exc:
            logger.warning("Failed to dispatch scraping notification: %s", exc)
