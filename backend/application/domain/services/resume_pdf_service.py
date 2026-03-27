"""Server-side PDF generation for resume exports."""
import json
import re
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright

from application.domain.exceptions.domain_exceptions import DomainException
from configuration.settings_configuration import settings


class ResumePdfService:
    RESUME_STORAGE_KEY = "kids-jobs:resume-draft:v1"
    DEFAULT_LOCALE = "pt"

    @classmethod
    def get_storage_key(cls, locale: str) -> str:
        return f"{cls.RESUME_STORAGE_KEY}:{locale}"

    @classmethod
    def get_storage_keys(cls, locale: str) -> list[str]:
        keys = [cls.get_storage_key(locale)]
        if locale == cls.DEFAULT_LOCALE:
            keys.append(cls.RESUME_STORAGE_KEY)
        return keys

    def render_resume_pdf(self, *, resume_payload: dict, locale: str = DEFAULT_LOCALE) -> bytes:
        query = urlencode({"autoprint": "0", "locale": locale})
        export_url = f"{settings.frontend_app_url.rstrip('/')}/resume/export?{query}"

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage"],
                )
                context = browser.new_context(viewport={"width": 1280, "height": 1800}, device_scale_factor=1)
                context.add_init_script(script=self._build_storage_seed_script(resume_payload, locale))
                page = context.new_page()
                page.goto(export_url, wait_until="networkidle", timeout=60_000)
                page.emulate_media(media="print")
                page.wait_for_selector('[data-resume-ready="true"]', timeout=60_000)
                page.wait_for_function(
                    "() => !document.fonts || document.fonts.status === 'loaded'",
                    timeout=60_000,
                )
                page.wait_for_function(
                    "() => Array.from(document.images).every((image) => image.complete)",
                    timeout=60_000,
                )
                page.wait_for_timeout(500)
                pdf_bytes = page.pdf(
                    format="A4",
                    print_background=True,
                    prefer_css_page_size=True,
                    margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
                )
                context.close()
                browser.close()
                return pdf_bytes
        except Exception as exc:  # pragma: no cover - depends on browser runtime
            raise DomainException(self._summarize_exception(exc), status_code=500) from exc

    @classmethod
    def _build_storage_seed_script(cls, payload: dict, locale: str) -> str:
        serialized_payload = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        storage_commands = "".join(
            f"window.localStorage.setItem({json.dumps(storage_key)}, {json.dumps(serialized_payload)});"
            for storage_key in cls.get_storage_keys(locale)
        )
        return (
            "(() => {"
            "try {"
            f"{storage_commands}"
            "} catch (error) {"
            "console.error('resume pdf localStorage seed failed', error);"
            "}"
            "})();"
        )

    @staticmethod
    def _summarize_exception(exc: Exception) -> str:
        message = str(exc).strip().splitlines()[0]

        if "ERR_CONNECTION_RESET" in message:
            return "Falha de conexão com o frontend ao gerar PDF (ERR_CONNECTION_RESET)"
        if "ERR_CONNECTION_REFUSED" in message:
            return "Falha de conexão com o frontend ao gerar PDF (ERR_CONNECTION_REFUSED)"
        if "Timeout" in message:
            return "Timeout ao renderizar o curriculo em /resume/export"

        sanitized = re.sub(r"\s+at https?://\S+", "", message)
        return f"Falha ao gerar PDF do curriculo: {sanitized}"
