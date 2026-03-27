"""
ChãoZão Scraper
Scrapes agribusiness property listings from ChãoZão
"""
from __future__ import annotations

import json
import re
from typing import Optional
from urllib.parse import urlencode, urljoin

from adapters.outbound.scraping.http_scraper import HTTPScraper
from application.domain.entities.scraped_item import ScrapedItem
from application.domain.entities.scraper_config import ScraperConfig, ScraperMetadata
from application.domain.shared.scraper_types import ScrapingCategory, ScrapingStrategy, SourceType


class ChaozaoScraper(HTTPScraper):
    """Scraper for ChãoZão rural property listings."""

    @staticmethod
    def get_default_config() -> ScraperConfig:
        return ScraperConfig(
            metadata=ScraperMetadata(
                name="chaozao",
                display_name="ChãoZão",
                description="Scraper de propriedades rurais do ChãoZão",
                category=ScrapingCategory.AGRIBUSINESS,
                source_type=SourceType.HTTP,
                version="1.0.0",
            ),
            base_url="https://www.chaozao.com.br",
            endpoint="/imoveis-rurais-a-venda/",
            enabled=True,
            rate_limit_delay=1.5,
            max_items_per_run=100,
            strategy=ScrapingStrategy.BROWSER_PLAYWRIGHT,
            extra_config={
                "listing_api_base_url": "https://dev.chaozao.com.br",
                "listing_api_endpoint": "/properties/combined-search",
                "listing_api_page_size": 100,
                "playwright_wait_until": "domcontentloaded",
                "playwright_wait_after_load_ms": 2600,
                "playwright_persistent_session": True,
                # Lógica reaproveitável para páginas com scroll infinito.
                "playwright_infinite_scroll_enabled": True,
                "playwright_infinite_scroll_max_rounds": 14,
                "playwright_infinite_scroll_pause_ms": 1200,
                "playwright_infinite_scroll_stable_rounds": 3,
                # Lógica reaproveitável para componentes lazy (ex.: mapa).
                "playwright_post_load_click_locators": [
                    "button:has-text('Carregar mapa')",
                    "button:has-text('Ver mapa')",
                ],
                "playwright_post_click_wait_ms": 1700,
            },
        )

    def __init__(self, config: Optional[ScraperConfig] = None):
        super().__init__(config)

    def scrape(self) -> list[ScrapedItem]:
        items: list[ScrapedItem] = []
        try:
            list_url = self.config.get_full_url()
            self.logger.info("Scraping ChãoZão list from: %s", list_url)

            detail_urls = self._collect_listing_urls(list_url)
            if not detail_urls:
                self.logger.warning("No listing detail URLs found on ChãoZão list page")
                return items

            for idx, detail_url in enumerate(detail_urls):
                if self.config.max_items_per_run and idx >= self.config.max_items_per_run:
                    break
                try:
                    detail_response = self._fetch_detail_page(detail_url)
                    if not detail_response:
                        continue

                    item = self._parse_listing_detail(detail_url, detail_response.text)
                    if item:
                        items.append(item)
                except Exception as exc:
                    self.logger.error("Error parsing ChãoZão detail %s: %s", detail_url, exc)

            self.logger.info("Scraped %s items from ChãoZão", len(items))
            return items
        except Exception as exc:
            self.logger.error("Error scraping ChãoZão: %s", exc)
            return items

    def scrape_url(self, url: str) -> Optional[ScrapedItem]:
        detail_url = self._normalize_listing_url(url)
        if not detail_url:
            return None

        response = self._fetch_detail_page(detail_url)
        if not response:
            return None
        return self._parse_listing_detail(detail_url, response.text)

    def _fetch_detail_page(self, detail_url: str):
        response = self._fetch_page_with_strategy(detail_url, ScrapingStrategy.HTTP_ANTIBOT)
        if response:
            return response

        # Fallback operacional quando o HTML simples falhar.
        return self._fetch_page_with_strategy(detail_url, ScrapingStrategy.BROWSER_PLAYWRIGHT)

    def _collect_listing_urls(self, list_url: str) -> list[str]:
        preferred_target = self.config.max_items_per_run or None
        api_urls = self._extract_listing_urls_via_api(target_count=preferred_target)
        if api_urls:
            return api_urls

        list_response = self.fetch_page(list_url)
        if not list_response:
            return []
        return self._extract_listing_urls(list_response.text)

    def _extract_listing_urls_via_api(self, target_count: Optional[int] = None) -> list[str]:
        page = 1
        total_pages: Optional[int] = None
        collected: list[str] = []
        seen: set[str] = set()

        while True:
            payload = self._fetch_listing_api_page(page)
            if not payload:
                break

            properties = payload.get("properties")
            if not isinstance(properties, list) or not properties:
                break

            for property_data in properties:
                detail_url = self._build_listing_url_from_api_property(property_data)
                if not detail_url or detail_url in seen:
                    continue
                seen.add(detail_url)
                collected.append(detail_url)
                if target_count and len(collected) >= target_count:
                    return collected

            if total_pages is None:
                total_pages = self._safe_int(payload.get("totalPages"))
            if total_pages is not None and page >= total_pages:
                break
            page += 1

        return collected

    def _fetch_listing_api_page(self, page: int) -> Optional[dict]:
        api_url = self._build_listing_api_url(page)
        response = self._fetch_page_with_strategy(api_url, ScrapingStrategy.HTTP_ANTIBOT)
        if not response:
            return None

        try:
            payload = json.loads(response.text)
        except Exception as exc:
            self.logger.warning("Invalid ChãoZão listing API payload for page %s: %s", page, exc)
            return None

        if not isinstance(payload, dict):
            return None
        return payload

    def _build_listing_api_url(self, page: int) -> str:
        base_url = str(self.config.extra_config.get("listing_api_base_url", "https://dev.chaozao.com.br")).rstrip("/")
        endpoint = str(self.config.extra_config.get("listing_api_endpoint", "/properties/combined-search")).strip()
        page_size = max(15, self._safe_int(self.config.extra_config.get("listing_api_page_size")) or 100)
        query = urlencode(
            {
                "pageSize": page_size,
                "type": "comprar",
                "city": "",
                "state": "",
                "areaType": "",
                "minPrice": "",
                "maxPrice": "",
                "minSize": "",
                "maxSize": "",
                "sortBy": "new",
                "owner": "",
                "permuta": "",
                "page": max(1, page),
            }
        )
        return f"{base_url}/{endpoint.lstrip('/')}?{query}"

    def _build_listing_url_from_api_property(self, property_data: dict) -> Optional[str]:
        if not isinstance(property_data, dict):
            return None

        external_url = property_data.get("externalUrl")
        normalized_external = self._normalize_listing_url(str(external_url).strip()) if external_url else None
        if normalized_external:
            return normalized_external

        slug = str(property_data.get("slug") or "").strip().strip("/")
        code = str(property_data.get("code") or "").strip().strip("/")
        if not slug or not code:
            return None
        return self._normalize_listing_url(f"/imovel/{slug}/{code.upper()}/")

    def _fetch_page_with_strategy(self, url: str, strategy: ScrapingStrategy):
        original_strategy = self.config.strategy
        try:
            self.config.strategy = strategy
            return self.fetch_page(url)
        finally:
            self.config.strategy = original_strategy

    def _extract_listing_urls(self, html: str) -> list[str]:
        soup = self.parse_html(html)
        preferred_urls: list[str] = []
        fallback_urls: list[str] = []

        for anchor in soup.select("a[href*='/imovel/']"):
            href = anchor.get("href", "")
            normalized = self._normalize_listing_url(href)
            if normalized:
                text = " ".join(anchor.get_text(" ", strip=True).split()).lower()
                if "detalhe" in text:
                    preferred_urls.append(normalized)
                else:
                    fallback_urls.append(normalized)

        urls: list[str] = preferred_urls + fallback_urls

        # Fallback: alguns cards chegam serializados no HTML/script da listagem.
        for match in re.findall(r"(https?://(?:www\.)?chaozao\.com\.br/imovel/[^\s\"'\\]+)", html):
            normalized = self._normalize_listing_url(match)
            if normalized:
                urls.append(normalized)

        unique: list[str] = []
        seen: set[str] = set()
        for url in urls:
            if url in seen:
                continue
            seen.add(url)
            unique.append(url)
        return unique

    def _normalize_listing_url(self, href: str) -> Optional[str]:
        if not href:
            return None

        cleaned = href.strip().replace("\\", "")
        if not cleaned:
            return None

        absolute = cleaned if cleaned.startswith("http") else urljoin(self.config.base_url, cleaned)
        absolute = absolute.split("#", 1)[0].split("?", 1)[0]
        if "/imovel/" not in absolute:
            return None
        if not absolute.endswith("/"):
            absolute = f"{absolute}/"
        return absolute

    @staticmethod
    def _safe_int(value) -> Optional[int]:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _parse_listing_detail(self, detail_url: str, html: str) -> Optional[ScrapedItem]:
        soup = self.parse_html(html)
        listing_ld = self._extract_real_estate_listing_ldjson(soup)
        page_text = " ".join(soup.get_text(" ", strip=True).split())

        title = self._extract_title(soup, listing_ld, detail_url, html)
        description = self._extract_description(soup, listing_ld, page_text, html)
        price = self._extract_price(soup, listing_ld, page_text, html)
        area_hectares = self._extract_area_hectares(listing_ld, page_text, html)

        structured_city, structured_state = self._extract_structured_city_state_from_html(html)
        title_city, title_state = self._extract_city_state_from_title(title)
        city = structured_city or title_city or self._extract_city_from_title(title)
        state = structured_state or title_state or self._extract_state_from_description(description or page_text)

        listing_type = self._extract_listing_type(page_text, html)
        riverbank = "cabeceira" in page_text.lower()
        irrigation = self._extract_irrigation(description or page_text)

        images = self._extract_images(soup, listing_ld, html)
        contact_phone, contact_email = self._extract_contacts(page_text, html)
        latitude = self._extract_float_from_html(html, "latitude")
        longitude = self._extract_float_from_html(html, "longitude")
        if latitude is None:
            latitude = self._extract_dms_coordinate_from_html(html, "lat")
        if longitude is None:
            longitude = self._extract_dms_coordinate_from_html(html, "long")
        if latitude is None or longitude is None:
            maps_latitude, maps_longitude = self.extract_coordinates_from_google_maps_text(html)
            if latitude is None:
                latitude = maps_latitude
            if longitude is None:
                longitude = maps_longitude

        attributes: dict = {}
        if area_hectares is not None:
            attributes["area_hectares"] = area_hectares
        if listing_type:
            attributes["listing_type"] = listing_type
        if riverbank:
            attributes["riverbank"] = True
        if irrigation is not None:
            attributes["irrigation"] = irrigation

        topography_text = self._extract_topography(description or page_text)
        if topography_text and (description or "").lower().find("topografia") == -1:
            description = f"{(description or '').strip()} Topografia: {topography_text}".strip()

        scraped_data = {
            "title": title,
            "description": description,
            "price": price,
            "currency": "BRL",
            "state": state,
            "city": city,
            "contact_name": "Chãozão",
            "contact_phone": contact_phone,
            "contact_email": contact_email,
            "location": {
                "latitude": latitude,
                "longitude": longitude,
            } if latitude is not None or longitude is not None else None,
            "images": images,
            "attributes": attributes,
        }
        return self.build_scraped_item(url=detail_url, scraped_data=scraped_data)

    def _extract_real_estate_listing_ldjson(self, soup) -> dict:
        for script in soup.select("script[type='application/ld+json']"):
            raw = (script.get_text() or "").strip()
            if not raw:
                continue
            try:
                parsed = json.loads(raw)
            except Exception:
                continue

            if isinstance(parsed, dict) and parsed.get("@type") == "RealEstateListing":
                return parsed
        return {}

    def _extract_title(self, soup, listing_ld: dict, detail_url: str, html: str) -> Optional[str]:
        for h1 in soup.select("h1"):
            title = self._sanitize_title_candidate(" ".join(h1.get_text(" ", strip=True).split()))
            if title:
                return title

        title_ld = listing_ld.get("name")
        if isinstance(title_ld, str) and title_ld.strip():
            cleaned = self._sanitize_title_candidate(" ".join(title_ld.split()))
            if cleaned:
                return cleaned

        property_type, city_name, state_name = self._extract_title_parts_from_html(html)
        if property_type and city_name and state_name:
            synthesized = self._sanitize_title_candidate(f"{property_type} em {city_name} - {state_name}")
            if synthesized:
                return synthesized

        slug = detail_url.rstrip("/").split("/")[-2]
        if not slug:
            return None
        slug_main = slug.split("-com-area-", 1)[0]
        slug_main = slug_main.split("-cod-", 1)[0]
        return slug_main.replace("-", " ").title().strip() or None

    def _extract_description(self, soup, listing_ld: dict, page_text: str, html: str) -> Optional[str]:
        html_description = self._extract_best_description_from_html(html)
        if html_description:
            return html_description

        description_ld = listing_ld.get("description")
        if isinstance(description_ld, str) and description_ld.strip():
            return " ".join(description_ld.split())

        # Fallback para seção visual da página.
        heading = soup.find(lambda tag: tag.name in {"h2", "h3"} and "descrição" in tag.get_text(strip=True).lower())
        if heading:
            parent_text = " ".join(heading.parent.get_text(" ", strip=True).split())
            if parent_text:
                return parent_text
        return page_text[:2000] if page_text else None

    def _extract_price(self, soup, listing_ld: dict, page_text: str, html: str) -> Optional[float]:
        structured_price = self._extract_float_from_html(html, "price")
        if structured_price is not None:
            return structured_price

        offers = listing_ld.get("offers")
        if isinstance(offers, dict):
            price_value = offers.get("price")
            if isinstance(price_value, (int, float)):
                return float(price_value)
            if isinstance(price_value, str):
                return self.parse_price(price_value)

        candidate = self.extract_text(soup, "h1 + p, strong, b")
        price = self.parse_price(candidate)
        if price is not None:
            return price
        price = self._parse_float_token(candidate or "")
        if price is not None:
            return price

        regex_match = re.search(r"(?:R\$\s*|\$\s*)?[\d\.]+,\d{2}", page_text, flags=re.IGNORECASE)
        return self._parse_float_token(regex_match.group(0)) if regex_match else None

    def _extract_area_hectares(self, listing_ld: dict, page_text: str, html: str) -> Optional[float]:
        structured_area = self._extract_float_from_html(html, "area")
        if structured_area is not None:
            area_type = self._extract_string_from_html(html, "areaType")
            area_type_token = self._normalize_area_type(area_type)
            if area_type_token in {"m2", "metro", "metros", "metro quadrado", "metros quadrados"}:
                return structured_area / 10000.0
            return structured_area

        # Campo estrutural comum no payload do app.
        total_area = self._extract_float_from_html(html, "totalArea")
        if total_area is not None:
            return total_area

        floor_size = listing_ld.get("floorSize")
        if isinstance(floor_size, dict):
            value = floor_size.get("value")
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                parsed = self._parse_float_token(value)
                if parsed is not None:
                    return parsed

        area_match = re.search(r"Área:\s*([\d\.,]+)\s*ha", page_text, flags=re.IGNORECASE)
        if not area_match:
            area_match = re.search(r"([\d\.,]+)\s*ha\b", page_text, flags=re.IGNORECASE)
        return self._parse_float_token(area_match.group(1)) if area_match else None

    def _extract_city_from_title(self, title: Optional[str]) -> Optional[str]:
        if not title:
            return None
        if "-" not in title:
            return None
        city_candidate = title.rsplit("-", 1)[-1].strip()
        return city_candidate or None

    def _extract_city_state_from_title(self, title: Optional[str]) -> tuple[Optional[str], Optional[str]]:
        if not title:
            return None, None

        cleaned_title = " ".join(title.split()).strip()
        match = re.search(r"\bem\s+(.+?)\s*-\s*([A-Za-zÀ-ÿ\s]{2,})$", cleaned_title, flags=re.IGNORECASE)
        if not match:
            return self._extract_city_from_title(cleaned_title), None

        left_city = " ".join(match.group(1).split()).strip(" -")
        right_text = " ".join(match.group(2).split()).strip(" -")
        right_state = self._extract_state_from_text_strict(right_text)

        if right_state:
            return left_city or right_text or None, right_state
        # Compatibilidade com padrão antigo: quando não identificar estado no lado direito,
        # considera o trecho após '-' como cidade.
        return right_text or None, None

    def _extract_structured_city_state_from_html(self, html: str) -> tuple[Optional[str], Optional[str]]:
        _, city_name, state_name = self._extract_title_parts_from_html(html)
        if not city_name:
            city_name = self._extract_string_from_html(html, "city")
        if not city_name:
            city_name = self._extract_string_from_html(html, "addressLocality")

        if not state_name:
            state_name = self._extract_string_from_html(html, "state")
        if not state_name:
            state_name = self._extract_string_from_html(html, "addressRegion")

        if city_name:
            city_name = " ".join(city_name.split()).strip(" -")
        state_uf = self._extract_state_from_text_strict(state_name) if state_name else None
        return city_name, state_uf

    def _extract_state_from_description(self, text: str) -> Optional[str]:
        # Regra solicitada: usar as duas últimas letras no padrão "- SP" da descrição.
        matches = re.findall(r"-\s*([A-Z]{2})\b", text.upper())
        if matches:
            return matches[-1]
        return self._extract_state_from_text_strict(text)

    def _sanitize_title_candidate(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return None

        cleaned = " ".join(value.split()).strip()
        if not cleaned:
            return None

        cleaned = re.sub(r"^\s*Cod\.\s*:\s*[A-Z0-9]+\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(
            r"Você não está logado.*?favoritar um imóvel\.\s*Registrar\s*Entrar",
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = cleaned.replace("Você não está logado", " ")
        cleaned = cleaned.replace("Você precisa entrar em sua conta para favoritar um imóvel.", " ")
        cleaned = re.sub(r"\bRegistrar\b", " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bEntrar\b", " ", cleaned, flags=re.IGNORECASE)
        cleaned = " ".join(cleaned.split()).strip(" -|")

        if not cleaned:
            return None
        lowered = cleaned.lower()
        if "você não está logado" in lowered or "favoritar um imóvel" in lowered:
            return None
        return cleaned

    def _extract_title_parts_from_html(self, html: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Fallback para montar título quando H1 vier poluído:
        propertyType + city + state do payload embutido da página.
        """
        for variant in self._html_variants(html):
            pattern = (
                r'"propertyType":"((?:\\.|[^"\\]){2,120})"'
                r'[^{}]{0,4000}?'
                r'"city":"((?:\\.|[^"\\]){2,120})"'
                r'[^{}]{0,4000}?'
                r'"state":"((?:\\.|[^"\\]){2,120})"'
            )
            match = re.search(pattern, variant)
            if not match:
                continue

            property_type = self._decode_json_string(match.group(1))
            city_name = self._decode_json_string(match.group(2))
            state_name = self._decode_json_string(match.group(3))

            property_type = " ".join(property_type.split()).strip()
            city_name = " ".join(city_name.split()).strip()
            state_name = " ".join(state_name.split()).strip()
            if not property_type or not city_name or not state_name:
                continue
            return property_type, city_name, state_name
        return None, None, None

    def _extract_listing_type(self, page_text: str, html: str) -> Optional[str]:
        business_type = self._extract_string_from_html(html, "businessType")
        if business_type:
            normalized = business_type.strip().upper()
            if normalized in {"SALE", "SELL"}:
                return "sale"
            if normalized in {"RENT", "RENTAL", "LEASE"}:
                return "rent"
            if normalized in {"AUCTION"}:
                return "auction"

        normalized = page_text.lower()
        if " venda " in f" {normalized} ":
            return "sale"
        if " arrendamento " in f" {normalized} " or " aluguel " in f" {normalized} ":
            return "rent"
        if " leilão " in f" {normalized} " or " leilao " in f" {normalized} ":
            return "auction"
        return "catalog"

    def _extract_irrigation(self, text: str) -> Optional[bool]:
        normalized = text.lower()
        if "irrigação" in normalized or "irrigacao" in normalized:
            return True
        return None

    def _extract_topography(self, text: str) -> Optional[str]:
        match = re.search(r"Topografia:\s*([^:]{5,120})", text, flags=re.IGNORECASE)
        if not match:
            return None
        topography = " ".join(match.group(1).split()).strip(" .-")
        return topography or None

    def _extract_images(self, soup, listing_ld: dict, html: str) -> list[str]:
        images_raw = listing_ld.get("image")
        urls: list[str] = []
        if isinstance(images_raw, list):
            urls.extend([str(item).strip() for item in images_raw if str(item).strip()])
        elif isinstance(images_raw, str) and images_raw.strip():
            urls.append(images_raw.strip())

        # Captura imagens do carrossel horizontal serializadas no payload da página.
        urls.extend(re.findall(r"https://objectstorage[^\s\"'\\]+\.(?:jpg|jpeg|png|webp)", html, flags=re.IGNORECASE))

        if not urls:
            for img in soup.select("img[src]"):
                src = (img.get("src") or "").strip()
                if not src:
                    continue
                if "objectstorage" in src or "/media/" in src:
                    urls.append(src)

        unique: list[str] = []
        seen: set[str] = set()
        for url in urls:
            cleaned = url.split("?", 1)[0]
            if not self._is_supported_image_url(cleaned):
                continue
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            unique.append(cleaned)
        return unique

    def _extract_contacts(self, page_text: str, html: str) -> tuple[Optional[str], Optional[str]]:
        email = self._extract_string_from_html(html, "email")
        if not email:
            email_match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", page_text)
            email = email_match.group(0) if email_match else None

        phone = self._extract_phone_from_commercial_block(page_text)
        if not phone:
            phone = self._extract_string_from_html(html, "telNumber")
        if not phone:
            phone = self._extract_string_from_html(html, "telephone")
        if not phone:
            phone_match = re.search(
                r"(?:\+?55\s?)?(?:\(?\d{2}\)?\s?)?\d{4,5}[-\s]?\d{4}",
                page_text,
            )
            phone = phone_match.group(0) if phone_match else None

        if phone:
            phone = "".join(ch for ch in phone if ch.isdigit())
        return phone, email

    def _extract_best_description_from_html(self, html: str) -> Optional[str]:
        candidates: list[str] = []
        for variant in self._html_variants(html):
            candidates.extend(re.findall(r'"description":"((?:\\.|[^"\\]){20,6000})"', variant))
        if not candidates:
            return None

        best: Optional[str] = None
        for raw in candidates:
            decoded = self._decode_json_string(raw)
            cleaned = " ".join(decoded.split())
            if not cleaned:
                continue
            if best is None or len(cleaned) > len(best):
                best = cleaned
        return best

    def _extract_phone_from_commercial_block(self, text: str) -> Optional[str]:
        match = re.search(
            r"Comercial[^0-9]{0,20}((?:\+?55\s?)?(?:\(?\d{2}\)?\s?)?\d{4,5}[-\s]?\d{4})",
            text,
            flags=re.IGNORECASE,
        )
        if match:
            return match.group(1)
        return None

    def _extract_string_from_html(self, html: str, key: str) -> Optional[str]:
        pattern = rf'"{re.escape(key)}"\s*:\s*"((?:\\.|[^"\\])*)"'
        for variant in self._html_variants(html):
            match = re.search(pattern, variant)
            if not match:
                continue
            decoded = self._decode_json_string(match.group(1))
            cleaned = " ".join(decoded.split())
            if cleaned:
                return cleaned
        return None

    def _extract_float_from_html(self, html: str, key: str) -> Optional[float]:
        pattern = rf'"{re.escape(key)}"\s*:\s*(-?\d+(?:\.\d+)?)'
        for variant in self._html_variants(html):
            match = re.search(pattern, variant)
            if not match:
                continue
            try:
                return float(match.group(1))
            except ValueError:
                continue
        return None

    def _extract_dms_coordinate_from_html(self, html: str, key: str) -> Optional[float]:
        raw_value = self._extract_string_from_html(html, key)
        if not raw_value:
            return None
        return self._parse_dms_coordinate(raw_value)

    @staticmethod
    def _parse_dms_coordinate(value: str) -> Optional[float]:
        if not value:
            return None
        normalized = " ".join(value.split()).strip()
        match = re.search(
            r"(\d{1,3})\D+(\d{1,2})\D+(\d{1,2}(?:[.,]\d+)?)\D*([NSEWO])",
            normalized,
            flags=re.IGNORECASE,
        )
        if not match:
            return None

        degrees = float(match.group(1))
        minutes = float(match.group(2))
        seconds = float(match.group(3).replace(",", "."))
        direction = match.group(4).upper()

        decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
        if direction in {"S", "W", "O"}:
            decimal *= -1.0
        return decimal

    @staticmethod
    def _is_supported_image_url(url: str) -> bool:
        if not url:
            return False
        lowered = url.lower()
        if "youtube.com" in lowered or "youtu.be" in lowered or "vimeo.com" in lowered:
            return False
        if re.search(r"\.(?:jpg|jpeg|png|webp|gif|bmp|avif|svg)$", lowered):
            return True
        return "s3files.chaozao.com.br" in lowered or "objectstorage" in lowered

    def _extract_state_from_text_strict(self, text: Optional[str]) -> Optional[str]:
        if not text:
            return None
        cleaned = " ".join(text.split()).strip()
        if not cleaned:
            return None

        # 1) UF explícita.
        for token in re.findall(r"\b([A-Za-z]{2})\b", cleaned):
            state_candidate = token.upper()
            if state_candidate in self.BRAZIL_UF:
                return state_candidate

        # 2) Nome completo do estado.
        normalized = self._normalize_ascii_text(cleaned).lower()
        normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
        normalized = re.sub(r"\s{2,}", " ", normalized).strip()
        for state_name, state_uf in self.BRAZIL_STATE_NAME_TO_UF.items():
            if re.search(rf"\b{re.escape(state_name)}\b", normalized):
                return state_uf
        return None

    @staticmethod
    def _normalize_area_type(value: Optional[str]) -> str:
        if not value:
            return ""
        normalized = ChaozaoScraper._normalize_ascii_text(value).lower()
        normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
        normalized = re.sub(r"\s{2,}", " ", normalized).strip()
        return normalized

    @staticmethod
    def _html_variants(html: str) -> list[str]:
        variants = [html]
        unescaped = html.replace('\\"', '"').replace("\\u0026", "&").replace("\\/", "/")
        if unescaped != html:
            variants.append(unescaped)
        return variants

    @staticmethod
    def _decode_json_string(value: str) -> str:
        try:
            return json.loads(f"\"{value}\"")
        except Exception:
            return value

    @staticmethod
    def _parse_float_token(value: str) -> Optional[float]:
        raw = (value or "").strip()
        if not raw:
            return None
        cleaned = re.sub(r"[^0-9,\.\-]", "", raw)
        if not cleaned:
            return None
        if "," in cleaned and "." in cleaned:
            normalized = cleaned.replace(".", "").replace(",", ".")
        elif "," in cleaned:
            normalized = cleaned.replace(",", ".")
        else:
            normalized = cleaned
        try:
            return float(normalized)
        except ValueError:
            return None
