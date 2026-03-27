"""
HTTP Scraper — Base class for HTTP-based scrapers (Outbound Adapter)
Uses requests + BeautifulSoup for traditional web scraping.
"""
from __future__ import annotations

import os
import random
import re
import time
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

from adapters.outbound.scraping.base_scraper import BaseScraper
from application.domain.entities.scraper_config import ScraperConfig
from application.domain.shared.scraper_types import ScrapingStrategy

DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Safari/605.1.15",
]

BLOCKED_STATUS_CODES = {403, 429}


@dataclass
class BrowserFetchResponse:
    """Lightweight response used by browser-based fetch strategy."""

    text: str
    status_code: int
    url: str

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code} for url: {self.url}")


class HTTPScraper(BaseScraper):
    """
    Base class for HTTP scrapers.

    Provides:
      - fetch_page() with retry + exponential backoff + rate limiting
      - parse_html() with BeautifulSoup
      - extract_text() / extract_attr() CSS selector helpers
    """

    def __init__(self, config: Optional[ScraperConfig] = None):
        super().__init__(config)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": DEFAULT_USER_AGENTS[0],
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )
        self._proxy_index = 0
        self.last_fetch_diagnostics: dict[str, Optional[str] | Optional[int] | bool] = {
            "strategy": None,
            "status_code": None,
            "blocked": False,
            "error": None,
            "proxy": None,
            "url": None,
            "title": None,
        }

    def _strategy(self) -> ScrapingStrategy:
        if self.config and self.config.strategy:
            return self.config.strategy
        return ScrapingStrategy.HTTP_BASIC

    def _user_agent_pool(self) -> list[str]:
        if self.config and self.config.user_agents:
            return self.config.user_agents
        return DEFAULT_USER_AGENTS

    def _proxy_pool(self) -> list[str]:
        if not self.config:
            return []
        raw_pool = self.config.extra_config.get("proxy_pool", [])
        if isinstance(raw_pool, str):
            return [p.strip() for p in raw_pool.split(",") if p.strip()]
        if isinstance(raw_pool, list):
            return [str(p).strip() for p in raw_pool if str(p).strip()]
        return []

    def _pick_proxy(self) -> Optional[str]:
        pool = self._proxy_pool()
        if not pool:
            return None
        proxy = pool[self._proxy_index % len(pool)]
        self._proxy_index += 1
        return proxy

    def _build_headers(self, strategy: ScrapingStrategy, extra_headers: Optional[dict] = None) -> dict:
        headers = dict(self.session.headers)
        if extra_headers:
            headers.update(extra_headers)

        if strategy == ScrapingStrategy.HTTP_ANTIBOT:
            headers["User-Agent"] = random.choice(self._user_agent_pool())
            headers.setdefault("Accept-Language", "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7")
            headers.setdefault("Cache-Control", "no-cache")
            headers.setdefault("Pragma", "no-cache")
        return headers

    def _extra_value(self, key: str, default=None):
        if not self.config:
            return default
        return self.config.extra_config.get(key, default)

    @staticmethod
    def _to_bool(value, default: bool = False) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
        return default

    @staticmethod
    def _to_int(value, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _playwright_session_dir(self) -> Path:
        configured = self._extra_value("playwright_session_dir")
        env_dir = os.getenv("SCRAPING_PLAYWRIGHT_SESSION_DIR")
        base_dir = str(configured or env_dir or "/data/playwright-sessions").strip()
        return Path(base_dir)

    def _playwright_wait_until(self) -> str:
        wait_until = str(self._extra_value("playwright_wait_until", "networkidle")).strip().lower()
        return wait_until if wait_until in {"load", "domcontentloaded", "networkidle", "commit"} else "networkidle"

    def _playwright_wait_after_load_ms(self) -> int:
        return self._to_int(self._extra_value("playwright_wait_after_load_ms", 2200), default=2200)

    def _playwright_persistent_session_enabled(self) -> bool:
        return self._to_bool(self._extra_value("playwright_persistent_session", True), default=True)

    def _playwright_headless_enabled(self) -> bool:
        env_default = self._to_bool(os.getenv("SCRAPING_PLAYWRIGHT_HEADLESS", "true"), default=True)
        return self._to_bool(self._extra_value("playwright_headless", env_default), default=env_default)

    def _playwright_headful_fallback_enabled(self) -> bool:
        env_default = self._to_bool(os.getenv("SCRAPING_PLAYWRIGHT_HEADFUL_FALLBACK", "false"), default=False)
        return self._to_bool(self._extra_value("playwright_headful_fallback", env_default), default=env_default)

    def _playwright_virtual_display_size(self) -> tuple[int, int]:
        raw = str(self._extra_value("playwright_virtual_display_size", "1440x960")).strip().lower()
        if "x" in raw:
            width_text, height_text = raw.split("x", 1)
            width = self._to_int(width_text, 1440)
            height = self._to_int(height_text, 960)
            return max(1024, width), max(720, height)
        return 1440, 960

    def _playwright_infinite_scroll_enabled(self) -> bool:
        return self._to_bool(self._extra_value("playwright_infinite_scroll_enabled", False), default=False)

    def _playwright_infinite_scroll_max_rounds(self) -> int:
        return max(1, self._to_int(self._extra_value("playwright_infinite_scroll_max_rounds", 10), default=10))

    def _playwright_infinite_scroll_pause_ms(self) -> int:
        return max(200, self._to_int(self._extra_value("playwright_infinite_scroll_pause_ms", 1200), default=1200))

    def _playwright_infinite_scroll_stable_rounds(self) -> int:
        return max(1, self._to_int(self._extra_value("playwright_infinite_scroll_stable_rounds", 2), default=2))

    def _playwright_post_load_click_locators(self) -> list[str]:
        raw = self._extra_value("playwright_post_load_click_locators", [])
        if isinstance(raw, list):
            return [str(item).strip() for item in raw if str(item).strip()]
        if isinstance(raw, str):
            text = raw.strip()
            if not text:
                return []
            separator = "||" if "||" in text else ","
            return [item.strip() for item in text.split(separator) if item.strip()]
        return []

    def _playwright_post_click_wait_ms(self) -> int:
        return max(300, self._to_int(self._extra_value("playwright_post_click_wait_ms", 1200), default=1200))

    def _playwright_block_resource_types(self) -> set[str]:
        raw = self._extra_value("playwright_block_resource_types", [])
        if isinstance(raw, str):
            values = [item.strip().lower() for item in raw.split(",") if item.strip()]
            return set(values)
        if isinstance(raw, list):
            return {str(item).strip().lower() for item in raw if str(item).strip()}
        return set()

    def _playwright_block_url_patterns(self) -> list[str]:
        raw = self._extra_value("playwright_block_url_patterns", [])
        if isinstance(raw, str):
            return [item.strip().lower() for item in raw.split(",") if item.strip()]
        if isinstance(raw, list):
            return [str(item).strip().lower() for item in raw if str(item).strip()]
        return []

    def _playwright_retry_count(self) -> int:
        return max(1, self._to_int(self._extra_value("playwright_retry_count", 1), default=1))

    def _playwright_retry_delay_ms(self) -> int:
        return max(0, self._to_int(self._extra_value("playwright_retry_delay_ms", 1000), default=1000))

    def _run_playwright_infinite_scroll(self, page) -> None:
        """
        Generic infinite-scroll routine for listing pages.
        Reusable across sites by enabling via scraper `extra_config`.
        """
        max_rounds = self._playwright_infinite_scroll_max_rounds()
        pause_ms = self._playwright_infinite_scroll_pause_ms()
        stable_target = self._playwright_infinite_scroll_stable_rounds()

        stable_rounds = 0
        last_height = -1
        for _ in range(max_rounds):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(pause_ms)
            current_height = page.evaluate("document.body.scrollHeight")

            if current_height == last_height:
                stable_rounds += 1
                if stable_rounds >= stable_target:
                    break
            else:
                stable_rounds = 0
            last_height = current_height

        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(300)

    def _run_playwright_post_load_clicks(self, page) -> None:
        """
        Generic routine to click UI controls after load.
        Useful for lazy components like map widgets (ex.: "Carregar mapa").
        """
        locators = self._playwright_post_load_click_locators()
        if not locators:
            return

        wait_ms = self._playwright_post_click_wait_ms()
        for locator_query in locators:
            try:
                locator = page.locator(locator_query).first
                if locator.count() == 0:
                    continue
                locator.scroll_into_view_if_needed(timeout=5000)
                locator.click(timeout=5000)
                page.wait_for_timeout(wait_ms)
            except Exception as click_exc:
                self.logger.debug("Playwright post-load click failed for locator '%s': %s", locator_query, click_exc)

    def _playwright_blocked_title_keywords(self) -> list[str]:
        raw = self._extra_value("playwright_blocked_title_keywords")
        if isinstance(raw, str):
            return [item.strip().lower() for item in raw.split(",") if item.strip()]
        if isinstance(raw, list):
            return [str(item).strip().lower() for item in raw if str(item).strip()]
        return [
            "operação inválida",
            "operacao invalida",
            "access denied",
            "forbidden",
            "request unsuccessful",
        ]

    @staticmethod
    def _extract_title_from_html(raw_html: str) -> str:
        match = re.search(r"<title[^>]*>(.*?)</title>", raw_html, re.I | re.S)
        if not match:
            return ""
        return BeautifulSoup(match.group(1), "html.parser").get_text(" ", strip=True)

    @staticmethod
    def _backoff_delay(attempt: int, blocked: bool = False) -> float:
        base = min(30.0, (2 ** attempt) + random.uniform(0.2, 1.2))
        if blocked:
            return base + random.uniform(1.0, 3.0)
        return base

    def fetch_page(self, url: str, method: str = "GET", **kwargs) -> Optional[requests.Response | BrowserFetchResponse]:
        """Fetch a page with retry logic and strategy-aware anti-bot options."""
        strategy = self._strategy()
        max_retries = self.config.max_retries if self.config else 3
        timeout = self.config.timeout if self.config else 30

        self.last_fetch_diagnostics = {
            "strategy": strategy.value,
            "status_code": None,
            "blocked": False,
            "error": None,
            "proxy": None,
            "url": url,
            "title": None,
        }

        if strategy == ScrapingStrategy.BROWSER_PLAYWRIGHT:
            return self._fetch_with_playwright(url=url, timeout=timeout)

        for attempt in range(max_retries):
            proxy = self._pick_proxy() if strategy == ScrapingStrategy.HTTP_ANTIBOT else None
            try:
                request_kwargs = dict(kwargs)
                extra_headers = request_kwargs.pop("headers", None)
                request_kwargs["headers"] = self._build_headers(strategy=strategy, extra_headers=extra_headers)
                if proxy:
                    request_kwargs["proxies"] = {"http": proxy, "https": proxy}

                response = self.session.request(
                    method=method,
                    url=url,
                    timeout=timeout,
                    **request_kwargs,
                )

                status_code = response.status_code
                blocked = status_code in BLOCKED_STATUS_CODES
                self.last_fetch_diagnostics.update(
                    {
                        "status_code": status_code,
                        "blocked": blocked,
                        "error": None,
                        "proxy": proxy,
                    }
                )

                if blocked:
                    raise requests.HTTPError(f"Blocked with status {status_code} for {url}")

                response.raise_for_status()

                if self.config and self.config.rate_limit_delay:
                    time.sleep(self.config.rate_limit_delay)

                return response

            except requests.RequestException as e:
                self.last_fetch_diagnostics["error"] = str(e)
                self.logger.warning(f"Attempt {attempt + 1} failed for {url}: {e}")
                if attempt == max_retries - 1:
                    self.logger.error(f"Failed to fetch {url} after {max_retries} attempts")
                    return None

                time.sleep(self._backoff_delay(attempt, blocked=bool(self.last_fetch_diagnostics.get("blocked"))))

        return None

    def _fetch_with_playwright(self, url: str, timeout: int) -> Optional[BrowserFetchResponse]:
        """Fetch page using Playwright for heavily dynamic/anti-bot pages."""
        attempts = [self._playwright_headless_enabled()]
        if self._playwright_headful_fallback_enabled() and attempts[-1] is True:
            attempts.append(False)
        retry_count = self._playwright_retry_count()
        retry_delay_ms = self._playwright_retry_delay_ms()

        for index, headless in enumerate(attempts):
            mode = "headless" if headless else "headful"
            for retry_index in range(retry_count):
                response = self._fetch_with_playwright_once(url=url, timeout=timeout, headless=headless)
                if response is not None:
                    if self.config and self.config.rate_limit_delay:
                        time.sleep(self.config.rate_limit_delay)
                    return response

                blocked = bool(self.last_fetch_diagnostics.get("blocked"))
                error = self.last_fetch_diagnostics.get("error")
                is_last_retry = retry_index == retry_count - 1
                if blocked or is_last_retry:
                    break

                self.logger.info(
                    "Playwright fetch retry %s/%s for %s in %s mode after failure: %s",
                    retry_index + 2,
                    retry_count,
                    url,
                    mode,
                    error or "unknown error",
                )
                if retry_delay_ms:
                    time.sleep(retry_delay_ms / 1000.0)

            if index == len(attempts) - 1:
                return None

            blocked = bool(self.last_fetch_diagnostics.get("blocked"))
            error = self.last_fetch_diagnostics.get("error")
            if blocked:
                self.logger.info(
                    "Playwright fetch blocked for %s in %s mode; retrying with next browser mode",
                    url,
                    mode,
                )
            else:
                self.logger.info(
                    "Playwright fetch failed for %s in %s mode (%s); retrying with next browser mode",
                    url,
                    mode,
                    error or "unknown error",
                )

        return None

    def _fetch_with_playwright_once(
        self,
        url: str,
        timeout: int,
        *,
        headless: bool,
    ) -> Optional[BrowserFetchResponse]:
        """Single Playwright fetch attempt, optionally using a virtual display for headful mode."""
        try:
            from playwright.sync_api import sync_playwright  # type: ignore
        except Exception as exc:
            self.last_fetch_diagnostics.update(
                {
                    "status_code": None,
                    "blocked": False,
                    "error": f"Playwright unavailable: {exc}",
                    "proxy": None,
                }
            )
            self.logger.error("Playwright strategy selected but dependency/browser is unavailable: %s", exc)
            return None

        try:
            display_context = nullcontext()
            if not headless:
                try:
                    from pyvirtualdisplay import Display  # type: ignore
                except Exception as exc:
                    self.last_fetch_diagnostics.update(
                        {
                            "status_code": None,
                            "blocked": False,
                            "error": f"Virtual display unavailable: {exc}",
                            "proxy": None,
                        }
                    )
                    self.logger.error("Headful Playwright requested but virtual display is unavailable: %s", exc)
                    return None

            proxy = self._pick_proxy()
            wait_until = self._playwright_wait_until()
            wait_after_load_ms = self._playwright_wait_after_load_ms()
            use_persistent_session = self._playwright_persistent_session_enabled()
            warmup_url = str(self._extra_value("playwright_warmup_url", self.config.base_url if self.config else "")).strip()
            blocked_title_keywords = self._playwright_blocked_title_keywords()
            user_agent = random.choice(self._user_agent_pool())
            viewport_width, viewport_height = self._playwright_virtual_display_size()

            if not headless:
                display_context = Display(visible=False, size=(viewport_width, viewport_height), use_xauth=False)

            with display_context:
                with sync_playwright() as playwright:
                    launch_kwargs = {
                        "headless": headless,
                        "args": [
                            "--disable-blink-features=AutomationControlled",
                            "--disable-dev-shm-usage",
                            "--no-sandbox",
                            "--disable-gpu",
                            "--disable-software-rasterizer",
                            "--disable-features=VizDisplayCompositor",
                        ],
                    }
                    if proxy:
                        launch_kwargs["proxy"] = {"server": proxy}

                    browser = None
                    context = None

                    context_kwargs = {
                        "user_agent": user_agent,
                        "locale": "pt-BR",
                        "timezone_id": "America/Sao_Paulo",
                        "viewport": {"width": viewport_width, "height": viewport_height},
                    }

                    if use_persistent_session and headless:
                        session_root = self._playwright_session_dir()
                        session_root.mkdir(parents=True, exist_ok=True)
                        scraper_name = self.get_name().strip().lower() or "default"
                        mode_suffix = "headless" if headless else "headful"
                        session_path = session_root / f"{scraper_name}-{mode_suffix}"
                        session_path.mkdir(parents=True, exist_ok=True)

                        context = playwright.chromium.launch_persistent_context(
                            user_data_dir=str(session_path),
                            **launch_kwargs,
                            **context_kwargs,
                        )
                    else:
                        browser = playwright.chromium.launch(**launch_kwargs)
                        context = browser.new_context(**context_kwargs)

                    page = context.pages[0] if context.pages else context.new_page()
                    page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")

                    blocked_resource_types = self._playwright_block_resource_types()
                    blocked_url_patterns = self._playwright_block_url_patterns()
                    if blocked_resource_types or blocked_url_patterns:
                        def _route_handler(route) -> None:
                            request = route.request
                            resource_type = (request.resource_type or "").strip().lower()
                            request_url = (request.url or "").strip().lower()
                            should_block = resource_type in blocked_resource_types or any(
                                pattern in request_url for pattern in blocked_url_patterns
                            )
                            if should_block:
                                route.abort()
                                return
                            route.continue_()

                        page.route("**/*", _route_handler)

                    if warmup_url and warmup_url != url:
                        try:
                            page.goto(warmup_url, wait_until="domcontentloaded", timeout=timeout * 1000)
                            page.wait_for_timeout(1200)
                        except Exception as warmup_exc:
                            self.logger.debug("Playwright warmup failed for %s: %s", warmup_url, warmup_exc)

                    try:
                        response = page.goto(url, wait_until=wait_until, timeout=timeout * 1000)
                    except Exception:
                        response = page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
                    page.wait_for_timeout(wait_after_load_ms)
                    if self._playwright_infinite_scroll_enabled():
                        self._run_playwright_infinite_scroll(page)
                    self._run_playwright_post_load_clicks(page)

                    status_code = response.status if response else 200

                    content = ""
                    content_error = None
                    try:
                        content = page.content()
                    except Exception as exc:
                        content_error = exc
                        self.logger.warning("Playwright page.content() failed for %s: %s", url, exc)

                    title = ""
                    title_error = None
                    try:
                        title = (page.title() or "").strip()
                    except Exception as exc:
                        title_error = exc
                        self.logger.warning("Playwright page.title() failed for %s: %s", url, exc)

                    if not title and content:
                        title = self._extract_title_from_html(content)

                    title_normalized = title.lower()
                    blocked_by_title = any(keyword in title_normalized for keyword in blocked_title_keywords)
                    blocked = status_code in BLOCKED_STATUS_CODES or blocked_by_title

                    self.last_fetch_diagnostics.update(
                        {
                            "status_code": status_code,
                            "blocked": blocked,
                            "error": None,
                            "proxy": proxy,
                            "title": title,
                            "mode": "headless" if headless else "headful",
                        }
                    )

                    context.close()
                    if browser:
                        browser.close()

                    if blocked:
                        self.logger.warning(
                            "Playwright fetch blocked for %s with status %s in %s mode",
                            url,
                            status_code,
                            "headless" if headless else "headful",
                        )
                        return None

                    if not content:
                        fallback_error = content_error or title_error or RuntimeError("Playwright returned empty content")
                        self.last_fetch_diagnostics["error"] = str(fallback_error)
                        self.logger.error(
                            "Playwright fetch produced no HTML for %s in %s mode: %s",
                            url,
                            "headless" if headless else "headful",
                            fallback_error,
                        )
                        return None

                    return BrowserFetchResponse(text=content, status_code=status_code, url=url)
        except Exception as exc:
            self.last_fetch_diagnostics.update(
                {
                    "status_code": None,
                    "blocked": False,
                    "error": str(exc),
                    "proxy": None,
                    "mode": "headless" if headless else "headful",
                }
            )
            self.logger.error(
                "Playwright fetch failed for %s in %s mode: %s",
                url,
                "headless" if headless else "headful",
                exc,
            )
            return None

    def parse_html(self, html: str) -> BeautifulSoup:
        """Parse HTML content into BeautifulSoup"""
        return BeautifulSoup(html, "html.parser")

    def extract_text(self, element, selector: str, default: str = "") -> str:
        """Extract text from element using CSS selector"""
        if not element:
            return default
        found = element.select_one(selector)
        return found.get_text(strip=True) if found else default

    def extract_attr(self, element, selector: str, attr: str, default: str = "") -> str:
        """Extract attribute from element using CSS selector"""
        if not element:
            return default
        found = element.select_one(selector)
        return found.get(attr, default) if found else default
