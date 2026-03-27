"""
API Scraper — Base class for API-based scrapers (Outbound Adapter)
Uses requests for REST/GraphQL API calls.
"""
import time
from typing import Optional, Dict, Any

import requests

from adapters.outbound.scraping.base_scraper import BaseScraper
from application.domain.entities.scraper_config import ScraperConfig


class APIScraper(BaseScraper):
    """
    Base class for API scrapers (REST, GraphQL).

    Provides:
      - call_api() with retry + backoff
      - Auth setup (bearer, api_key, basic)
    """

    def __init__(self, config: Optional[ScraperConfig] = None):
        super().__init__(config)
        self.session = requests.Session()
        self._setup_auth()
        self.last_fetch_diagnostics: dict[str, Optional[str] | Optional[int] | bool] = {
            "status_code": None,
            "error": None,
            "url": None,
        }

    def _setup_auth(self):
        """Setup authentication from config credentials"""
        if not self.config or not self.config.auth_required:
            return

        creds = self.config.credentials
        auth_type = creds.get("type", "bearer")

        if auth_type == "bearer" and "token" in creds:
            self.session.headers["Authorization"] = f"Bearer {creds['token']}"
        elif auth_type == "api_key" and "api_key" in creds:
            key_name = creds.get("key_name", "X-API-Key")
            self.session.headers[key_name] = creds["api_key"]
        elif auth_type == "basic" and "username" in creds and "password" in creds:
            from requests.auth import HTTPBasicAuth
            self.session.auth = HTTPBasicAuth(creds["username"], creds["password"])

    def fetch_json(
        self,
        endpoint: str,
        method: str = "GET",
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        **kwargs,
    ) -> Optional[Dict[str, Any]]:
        """Make API call with retry logic"""
        url = f"{self.config.base_url}/{endpoint.lstrip('/')}" if self.config else endpoint
        max_retries = self.config.max_retries if self.config else 3
        timeout = self.config.timeout if self.config else 30

        self.last_fetch_diagnostics = {
            "status_code": None,
            "error": None,
            "url": url,
        }

        for attempt in range(max_retries):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    timeout=timeout,
                    **kwargs,
                )
                response.raise_for_status()
                self.last_fetch_diagnostics = {
                    "status_code": response.status_code,
                    "error": None,
                    "url": url,
                }

                if self.config and self.config.rate_limit_delay:
                    time.sleep(self.config.rate_limit_delay)

                return response.json()

            except requests.RequestException as e:
                status_code = None
                if isinstance(getattr(e, "response", None), requests.Response):
                    status_code = e.response.status_code
                self.last_fetch_diagnostics = {
                    "status_code": status_code,
                    "error": str(e),
                    "url": url,
                }
                self.logger.warning(f"API call attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    self.logger.error(f"API call failed after {max_retries} attempts")
                    return None
                time.sleep(2 ** attempt)

        return None

    def call_api(
        self,
        endpoint: str,
        method: str = "GET",
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        **kwargs,
    ) -> Optional[Dict[str, Any]]:
        return self.fetch_json(
            endpoint=endpoint,
            method=method,
            params=params,
            json_data=json_data,
            **kwargs,
        )
