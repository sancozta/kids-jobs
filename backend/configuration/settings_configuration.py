"""Runtime settings for kids-jobs backend."""
from urllib.parse import urlparse

from pydantic_settings import BaseSettings, SettingsConfigDict


def _normalize_origin(value: str | None) -> str | None:
    normalized = (value or "").strip().rstrip("/")
    return normalized or None


def _expand_localhost_variants(value: str | None) -> list[str]:
    origin = _normalize_origin(value)
    if not origin:
        return []

    parsed = urlparse(origin)
    variants = [origin]
    if parsed.hostname == "localhost":
        variants.append(origin.replace("localhost", "127.0.0.1", 1))
    elif parsed.hostname == "127.0.0.1":
        variants.append(origin.replace("127.0.0.1", "localhost", 1))

    deduplicated: list[str] = []
    for variant in variants:
        normalized_variant = _normalize_origin(variant)
        if normalized_variant and normalized_variant not in deduplicated:
            deduplicated.append(normalized_variant)
    return deduplicated


def _resolve_cors_origins(origins: list[str], frontend_app_url: str) -> list[str]:
    resolved: list[str] = []

    for value in [*origins, frontend_app_url]:
        for variant in _expand_localhost_variants(value):
            if variant not in resolved:
                resolved.append(variant)

    return resolved


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "kids-jobs-backend"
    debug: bool = False

    # Database
    database_url: str = "sqlite:///./kids-jobs.db"
    scraping_seed_on_startup: bool = True

    # Scraping
    scraping_proxy_pool: str = ""
    scraping_telegram_api_id: str = ""
    scraping_telegram_api_hash: str = ""
    scraping_telegram_session_string: str = ""
    scraping_telegram_jobs_ti_channels: str = ""
    scraping_telegram_ocr_enabled: bool = False
    scraping_telegram_ocr_languages: str = "por+eng"
    scraping_telegram_lookback_limit: int = 80
    rescrape_queue_batch_size: int = 10
    rescrape_queue_schedule_seconds: int = 60

    # Resume / email
    frontend_app_url: str = "http://localhost:3000"
    resend_api_key: str = ""
    resend_from_email: str = ""
    resend_from_name: str = "Kids Jobs"
    resend_personal_from_email: str = ""
    resend_personal_from_name: str = ""
    resend_company_reply_to_email: str = ""
    resend_personal_reply_to_email: str = ""

    # Server
    port: int = 8001
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    log_level: str = "INFO"

settings = Settings()
settings.cors_origins = _resolve_cors_origins(settings.cors_origins, settings.frontend_app_url)
