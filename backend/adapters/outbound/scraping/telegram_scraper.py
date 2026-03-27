from __future__ import annotations

import asyncio
import inspect
import io
import os
import re
from contextlib import suppress
from pathlib import Path
from typing import Any, Iterable, Optional

from adapters.outbound.persistence.telegram_offset_persistence_adapter import TelegramOffsetPersistenceAdapter
from adapters.outbound.scraping.base_scraper import BaseScraper
from application.domain.entities.scraper_config import ScraperConfig
from configuration.database_configuration import SessionLocal

try:
    import pytesseract
    from PIL import Image
except Exception:  # pragma: no cover - optional at runtime
    pytesseract = None
    Image = None

try:
    from telethon import TelegramClient, utils as telethon_utils
    from telethon.sessions import StringSession
except Exception:  # pragma: no cover - optional at runtime
    TelegramClient = None
    StringSession = None
    telethon_utils = None


class TelegramScraper(BaseScraper):
    """Base scraper for Telegram-backed sources."""

    def __init__(self, config: Optional[ScraperConfig] = None):
        super().__init__(config)
        self._client = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def _extra_value(self, key: str, default=None):
        if not self.config:
            return default
        return self.config.extra_config.get(key, default)

    def _env(self, key: str, default: str | None = None) -> str | None:
        value = os.getenv(key)
        if value is None:
            return default
        value = value.strip()
        return value or default

    def _bool_value(self, value: Any, default: bool = False) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
        return default

    def _int_value(self, value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _telegram_api_id(self) -> Optional[int]:
        raw = self._env("SCRAPING_TELEGRAM_API_ID") or self._extra_value("api_id")
        if raw is None:
            return None
        return self._int_value(raw, 0) or None

    def _telegram_api_hash(self) -> Optional[str]:
        raw = self._env("SCRAPING_TELEGRAM_API_HASH") or self._extra_value("api_hash")
        return str(raw).strip() if raw else None

    def _telegram_session_string(self) -> Optional[str]:
        raw = self._env("SCRAPING_TELEGRAM_SESSION_STRING") or self._extra_value("session_string")
        return str(raw).strip() if raw else None

    def _telegram_session_name(self) -> str:
        configured = self._env("SCRAPING_TELEGRAM_SESSION_NAME") or self._extra_value("session_name")
        if configured:
            return str(configured).strip()
        return self.get_name()

    def _telegram_channels(self) -> list[str]:
        raw = self._env("SCRAPING_TELEGRAM_JOBS_TI_CHANNELS") or self._extra_value("channels", [])
        if isinstance(raw, list):
            return [str(item).strip() for item in raw if str(item).strip()]
        if isinstance(raw, str):
            separator = "||" if "||" in raw else ","
            return [item.strip() for item in raw.split(separator) if item.strip()]
        return []

    def _telegram_lookback_limit(self) -> int:
        value = self._env("SCRAPING_TELEGRAM_LOOKBACK_LIMIT") or self._extra_value("lookback_limit", 80)
        return max(1, self._int_value(value, 80))

    def _telegram_ocr_enabled(self) -> bool:
        value = self._env("SCRAPING_TELEGRAM_OCR_ENABLED")
        if value is None:
            value = self._extra_value("ocr_enabled", False)
        return self._bool_value(value, default=False)

    def _telegram_ocr_languages(self) -> str:
        value = self._env("SCRAPING_TELEGRAM_OCR_LANGUAGES") or self._extra_value("ocr_languages", "por+eng")
        return str(value).strip() or "por+eng"

    def _telethon_available(self) -> bool:
        return TelegramClient is not None and StringSession is not None

    def _get_loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is not None and not self._loop.is_closed():
            asyncio.set_event_loop(self._loop)
            return self._loop

        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        return self._loop

    def _run_async(self, coroutine):
        if not inspect.isawaitable(coroutine):
            return coroutine
        loop = self._get_loop()
        return loop.run_until_complete(coroutine)

    def _get_client(self):
        if self._client is not None:
            return self._client

        if not self._telethon_available():
            self.logger.warning("Telethon não está instalado; scraper Telegram retornará vazio")
            return None

        api_id = self._telegram_api_id()
        api_hash = self._telegram_api_hash()
        if not api_id or not api_hash:
            self.logger.warning("Credenciais Telegram ausentes; defina SCRAPING_TELEGRAM_API_ID/API_HASH")
            return None

        session_string = self._telegram_session_string()
        if session_string:
            session = StringSession(session_string)
        else:
            session_dir = Path("/data/telegram-sessions")
            session_dir.mkdir(parents=True, exist_ok=True)
            session = str(session_dir / self._telegram_session_name())

        self._client = TelegramClient(session, api_id, api_hash, loop=self._get_loop())
        return self._client

    def _get_offset(self, chat_id: str) -> int:
        db = SessionLocal()
        try:
            adapter = TelegramOffsetPersistenceAdapter(db)
            offset = adapter.find(self.get_name(), chat_id)
            return int(offset.last_message_id) if offset else 0
        finally:
            db.close()

    def _save_offset(self, chat_id: str, last_message_id: int) -> None:
        db = SessionLocal()
        try:
            adapter = TelegramOffsetPersistenceAdapter(db)
            adapter.save_or_update(self.get_name(), chat_id, int(last_message_id))
        finally:
            db.close()

    def _extract_urls(self, text: str) -> list[str]:
        if not text:
            return []
        seen: set[str] = set()
        urls: list[str] = []
        for match in re.finditer(r"https?://[^\s)\]>]+", text, flags=re.IGNORECASE):
            value = match.group(0).rstrip('.,;')
            if value not in seen:
                seen.add(value)
                urls.append(value)
        return urls

    def _download_message_media_bytes(self, client, message) -> bytes | None:
        try:
            data = self._run_async(message.download_media(file=bytes))
        except Exception:
            self.logger.exception("Falha ao baixar mídia do Telegram para message_id=%s", getattr(message, "id", None))
            return None
        return data if isinstance(data, (bytes, bytearray)) else None

    def _ocr_image_bytes(self, image_bytes: bytes | None) -> Optional[str]:
        if not image_bytes or not self._telegram_ocr_enabled():
            return None
        if pytesseract is None or Image is None:
            self.logger.warning("OCR habilitado, mas pytesseract/Pillow não estão disponíveis")
            return None
        try:
            image = Image.open(io.BytesIO(image_bytes))
            text = pytesseract.image_to_string(image, lang=self._telegram_ocr_languages())
        except Exception:
            self.logger.exception("Falha ao executar OCR em imagem do Telegram")
            return None
        normalized = re.sub(r"\s+", " ", text or "").strip()
        return normalized or None

    def _build_public_message_link(self, entity, message_id: int) -> Optional[str]:
        username = getattr(entity, "username", None)
        if username:
            return f"https://t.me/{username}/{message_id}"
        return None

    def _build_canonical_message_url(self, entity, message_id: int) -> str:
        chat_id = self._get_canonical_chat_id(entity)
        return f"telegram://{chat_id}/{message_id}"

    def _get_canonical_chat_id(self, entity) -> int | str | None:
        if telethon_utils is not None:
            with suppress(Exception):
                return int(telethon_utils.get_peer_id(entity))
        return getattr(entity, "id", None)

    def _entity_matches_chat_id(self, entity, chat_id: str | int) -> bool:
        normalized = str(chat_id).strip()
        if not normalized:
            return False

        entity_id = str(getattr(entity, "id", "")).strip()
        canonical_id = str(self._get_canonical_chat_id(entity) or "").strip()
        candidates = {value for value in {entity_id, canonical_id} if value}

        if entity_id and not entity_id.startswith("-100"):
            candidates.add(f"-100{entity_id}")
        if normalized.startswith("-100"):
            candidates.add(normalized.removeprefix("-100"))

        return normalized in candidates

    def _resolve_entity_for_chat_id(self, client, chat_id: str | int):
        normalized = str(chat_id).strip()
        if not normalized:
            return None

        for channel_ref in self._telegram_channels():
            try:
                entity = self._run_async(client.get_entity(channel_ref))
            except Exception:
                continue
            if entity and self._entity_matches_chat_id(entity, normalized):
                return entity

        try:
            return self._run_async(client.get_entity(int(normalized)))
        except Exception:
            return None

    def _iter_channel_messages(self, client, channel_ref: str) -> Iterable[tuple[Any, Any]]:
        entity = self._run_async(client.get_entity(channel_ref))
        chat_id = str(getattr(entity, "id", channel_ref))
        min_id = self._get_offset(chat_id)
        limit = self._telegram_lookback_limit()
        messages = self._run_async(
            client.get_messages(entity, limit=limit, min_id=min_id)
        )
        iterable = list(reversed(list(messages or [])))
        return [(entity, message) for message in iterable]

    def _ensure_client_started(self):
        client = self._get_client()
        if client is None:
            return None
        if not client.is_connected():
            self._run_async(client.connect())
        if not self._run_async(client.is_user_authorized()):
            self.logger.warning("Sessão Telegram não autorizada; gere uma StringSession válida")
            return None
        return client

    def _shutdown_client(self) -> None:
        if self._client is None:
            return
        with suppress(Exception):
            if self._client.is_connected():
                self._run_async(self._client.disconnect())
        self._client = None
        if self._loop is not None and not self._loop.is_closed():
            with suppress(Exception):
                self._loop.stop()
            self._loop.close()
        self._loop = None
