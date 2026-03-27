"""
PNCP Licitacoes Scraper
Coleta licitacoes abertas a partir da API publica de consulta do PNCP.
"""
from __future__ import annotations

import html
import math
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Optional

from adapters.outbound.scraping.api_scraper import APIScraper
from application.domain.entities.scraped_item import ScrapedItem
from application.domain.entities.scraper_config import ScraperConfig, ScraperMetadata
from application.domain.shared.scraper_types import ScrapingCategory, SourceType


class PNCPLicitacoesScraper(APIScraper):
    """Scraper inicial de licitacoes via API publica do PNCP."""

    PAGE_SIZE = 50
    DEFAULT_LISTING_START_DATE = "20240101"
    DEFAULT_LISTING_END_DATE = "20991231"
    PUBLIC_URL_TEMPLATE = "https://pncp.gov.br/app/editais/{cnpj}/{ano}/{sequencial}"
    CONTROL_NUMBER_PATTERN = re.compile(r"(?P<cnpj>\d{14})-\d-(?P<sequencial>\d+)/(?P<ano>\d{4})")
    DETAIL_ROUTE_PATTERN = re.compile(r"/(?:app/)?editais/(?P<cnpj>\d{14})/(?P<ano>\d{4})/(?P<sequencial>\d+)\b")
    DEFAULT_TARGET_UFS = ["DF", "GO", "MG", "BA", "ES", "PR", "TO"]
    SOFTWARE_FOCUS_MIN_SCORE = 40
    SOFTWARE_SIGNAL_RULES = (
        ("licenciamento de software", 55, "software_licensing", "licenca"),
        ("licenca de software", 55, "software_licensing", "licenca"),
        ("licenca de uso de software", 60, "software_licensing", "licenca"),
        ("saas", 60, "software_licensing", "licenca"),
        ("fabrica de software", 65, "software_development", "fabrica_software"),
        ("desenvolvimento de software", 65, "software_development", "desenvolvimento"),
        ("desenvolvimento de sistemas", 60, "software_development", "desenvolvimento"),
        ("aplicacao web", 55, "software_development", "desenvolvimento"),
        ("aplicativo", 55, "software_development", "desenvolvimento"),
        ("sustentacao de sistemas", 55, "systems_maintenance", "sustentacao"),
        ("manutencao evolutiva de sistemas", 60, "systems_maintenance", "sustentacao"),
        ("manutencao corretiva de sistemas", 50, "systems_maintenance", "sustentacao"),
        ("business intelligence", 55, "data_bi", "servico_continuado"),
        ("power bi", 55, "data_bi", "servico_continuado"),
        ("analytics", 40, "data_bi", "servico_continuado"),
        ("dashboard", 35, "data_bi", "servico_continuado"),
        ("banco de dados", 45, "data_bi", "servico_continuado"),
        (" api ", 35, "mixed_ti", "implantacao"),
        ("integracao de sistemas", 45, "mixed_ti", "implantacao"),
        ("sistema informatizado", 45, "mixed_ti", "implantacao"),
        ("sistema integrado de gestao", 55, "mixed_ti", "implantacao"),
        ("sistema de gestao", 45, "mixed_ti", "implantacao"),
        ("sistema de informacao", 45, "mixed_ti", "implantacao"),
        ("sistema web", 45, "mixed_ti", "implantacao"),
        ("portal web", 40, "mixed_ti", "implantacao"),
        ("plataforma digital", 45, "mixed_ti", "implantacao"),
        ("software", 30, "other_ti", "outro"),
        (" erp ", 55, "software_licensing", "implantacao"),
        (" crm ", 55, "software_licensing", "implantacao"),
        ("computacao em nuvem", 50, "cloud_infra", "servico_continuado"),
        ("infraestrutura em nuvem", 50, "cloud_infra", "servico_continuado"),
        (" cloud ", 35, "cloud_infra", "servico_continuado"),
        (" nuvem ", 30, "cloud_infra", "servico_continuado"),
    )
    SOFTWARE_ANTI_PHRASES = (
        "cartucho",
        "toner",
        "impressora",
        "impressoras",
        "notebook",
        "notebooks",
        "computador",
        "computadores",
        "microcomputador",
        "microcomputadores",
        "mouse",
        "teclado",
        "monitor",
        "monitores",
        "scanner",
        "roteador",
        "switch",
        "cabeamento",
        "link de internet",
        "internet dedicada",
        "camera",
        "cameras",
        "nobreak",
        "equipamento de informatica",
        "equipamentos de informatica",
        "suprimento de informatica",
        "suprimentos de informatica",
        "material de expediente",
        "combustivel",
        "genero alimenticio",
        "veiculo",
        "veiculos",
    )

    @staticmethod
    def get_default_config() -> ScraperConfig:
        return ScraperConfig(
            metadata=ScraperMetadata(
                name="pncp_licitacoes",
                display_name="PNCP Licitações",
                description="Scraper de licitações públicas abertas via API oficial de consulta do PNCP",
                category=ScrapingCategory.TENDERS,
                source_type=SourceType.API,
                version="1.0.0",
            ),
            base_url="https://pncp.gov.br/api/consulta",
            enabled=True,
            timeout=30,
            rate_limit_delay=0.4,
            max_items_per_run=20000,
            extra_config={
                "target_ufs": PNCPLicitacoesScraper.DEFAULT_TARGET_UFS.copy(),
                "target_municipios_ibge": [],
                "listing_start_date": PNCPLicitacoesScraper.DEFAULT_LISTING_START_DATE,
                "listing_end_date": PNCPLicitacoesScraper.DEFAULT_LISTING_END_DATE,
            },
        )

    def scrape(self) -> list[ScrapedItem]:
        items: list[ScrapedItem] = []
        max_items = self.config.max_items_per_run or 20000
        seen_control_numbers: set[str] = set()

        scopes_state = [
            {"scope": scope, "page": 1, "done": False}
            for scope in self._build_listing_scopes()
        ]

        while len(items) < max_items and any(not state["done"] for state in scopes_state):
            progressed = False

            for state in scopes_state:
                if state["done"] or len(items) >= max_items:
                    continue

                payload = self.fetch_json(
                    "/v1/contratacoes/proposta",
                    params=self._build_listing_params(page=int(state["page"]), scope=state["scope"]),
                )
                page_entries = self._extract_listing_entries(payload)
                if not page_entries:
                    state["done"] = True
                    continue

                progressed = True

                for entry in page_entries:
                    item = self._build_item_from_summary(entry)
                    if item is None:
                        continue

                    source_record_id = item.scraped_data.attributes.get("source_record_id")
                    dedupe_key = source_record_id if isinstance(source_record_id, str) and source_record_id else item.url
                    if dedupe_key in seen_control_numbers:
                        continue
                    seen_control_numbers.add(dedupe_key)

                    items.append(item)
                    if len(items) >= max_items:
                        break

                total_pages = self._safe_int(payload.get("totalPaginas")) if isinstance(payload, dict) else None
                if total_pages is not None and int(state["page"]) >= total_pages:
                    state["done"] = True
                else:
                    state["page"] = int(state["page"]) + 1

            if not progressed:
                break

        return items

    def scrape_url(self, url: str) -> Optional[ScrapedItem]:
        normalized_url = self._normalize_scrape_url(url)
        self._reset_scrape_url_diagnostics(url=normalized_url or url)

        parts = self._extract_detail_parts_from_url(normalized_url)
        if parts is None:
            control_number = self._extract_control_number_from_url(normalized_url)
            if not control_number:
                return None
            parts = self._parse_control_number(control_number)
        if parts is None:
            return None

        cnpj, ano, sequencial = parts
        payload = self.fetch_json(f"/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}")
        if not isinstance(payload, dict):
            status_code = self.last_fetch_diagnostics.get("status_code")
            if status_code in {404, 410, 204}:
                self._mark_scrape_url_missing(reason="Contratação PNCP não encontrada", url=normalized_url or url)
            return None

        return self._build_item_from_detail(payload)

    def _build_listing_params(self, *, page: int, scope: Optional[dict[str, str]] = None) -> dict[str, object]:
        extra_config = self.config.extra_config if self.config and isinstance(self.config.extra_config, dict) else {}
        listing_start_date = self._normalize_listing_date(extra_config.get("listing_start_date")) or self.DEFAULT_LISTING_START_DATE
        listing_end_date = self._normalize_listing_date(extra_config.get("listing_end_date")) or self.DEFAULT_LISTING_END_DATE
        params: dict[str, object] = {
            "dataInicial": listing_start_date,
            "dataFinal": listing_end_date,
            "pagina": page,
            "tamanhoPagina": self.PAGE_SIZE,
        }
        if isinstance(scope, dict):
            params.update(scope)

        return params

    def _build_listing_scopes(self) -> list[dict[str, str]]:
        extra_config = self.config.extra_config if self.config and isinstance(self.config.extra_config, dict) else {}

        target_ufs = self._normalize_target_ufs(extra_config.get("target_ufs"))
        legacy_target_uf = self._normalize_text(extra_config.get("target_uf"))
        if legacy_target_uf:
            normalized_legacy_uf = legacy_target_uf.upper()
            if normalized_legacy_uf not in target_ufs:
                target_ufs.append(normalized_legacy_uf)

        target_municipios = self._normalize_target_municipios(extra_config.get("target_municipios_ibge"))
        legacy_target_municipio = self._normalize_ibge_code(extra_config.get("target_municipio_ibge"))
        if legacy_target_municipio and legacy_target_municipio not in target_municipios:
            target_municipios.append(legacy_target_municipio)

        scopes: list[dict[str, str]] = [{"uf": uf} for uf in target_ufs]
        scopes.extend({"codigoMunicipioIbge": codigo} for codigo in target_municipios)
        return scopes or [{}]

    @classmethod
    def _normalize_target_ufs(cls, value: Any) -> list[str]:
        normalized_values = cls._normalize_config_list(value)
        result: list[str] = []
        seen: set[str] = set()
        for item in normalized_values:
            uf = cls._normalize_text(item)
            if not uf:
                continue
            uf = uf.upper()
            if uf not in cls.BRAZIL_UF or uf in seen:
                continue
            seen.add(uf)
            result.append(uf)
        return result

    @classmethod
    def _normalize_target_municipios(cls, value: Any) -> list[str]:
        normalized_values = cls._normalize_config_list(value)
        result: list[str] = []
        seen: set[str] = set()
        for item in normalized_values:
            codigo = cls._normalize_ibge_code(item)
            if not codigo or codigo in seen:
                continue
            seen.add(codigo)
            result.append(codigo)
        return result

    @staticmethod
    def _normalize_config_list(value: Any) -> list[Any]:
        if isinstance(value, (list, tuple, set)):
            return [item for item in value if item is not None]
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return []

    @staticmethod
    def _normalize_ibge_code(value: Any) -> Optional[str]:
        digits = re.sub(r"\D", "", str(value or ""))
        return digits if len(digits) == 7 else None

    @staticmethod
    def _normalize_listing_date(value: Any) -> Optional[str]:
        digits = re.sub(r"\D", "", str(value or ""))
        return digits if len(digits) == 8 else None

    @staticmethod
    def _extract_listing_entries(payload: Optional[dict]) -> list[dict]:
        if not isinstance(payload, dict):
            return []
        data = payload.get("data")
        if not isinstance(data, list):
            return []
        return [entry for entry in data if isinstance(entry, dict)]

    def _build_item_from_summary(self, entry: dict) -> Optional[ScrapedItem]:
        if not self._is_entry_active(entry):
            return None
        return self._build_item(entry)

    def _build_item_from_detail(self, entry: dict) -> Optional[ScrapedItem]:
        if not self._is_entry_active(entry):
            return None
        return self._build_item(entry)

    def _build_item(self, entry: dict) -> Optional[ScrapedItem]:
        control_number = self._normalize_text(entry.get("numeroControlePNCP"))
        if not control_number:
            return None

        public_url = self._build_public_url(control_number)
        agency = entry.get("orgaoEntidade") if isinstance(entry.get("orgaoEntidade"), dict) else {}
        unit = entry.get("unidadeOrgao") if isinstance(entry.get("unidadeOrgao"), dict) else {}

        agency_name = self._normalize_text(agency.get("razaoSocial"))
        agency_tax_id = self._normalize_digits(agency.get("cnpj"))
        city = self._normalize_text(unit.get("municipioNome"))
        state = self._normalize_text(unit.get("ufSigla"))
        municipality_ibge = self._extract_municipality_ibge(unit)
        object_text = self._normalize_text(entry.get("objetoCompra"))
        complementary_info = self._normalize_text(entry.get("informacaoComplementar"))
        modality_name = self._normalize_text(entry.get("modalidadeNome"))
        notice_number = self._normalize_text(entry.get("numeroCompra"))
        process_number = self._normalize_text(entry.get("processo"))
        status_name = self._normalize_text(entry.get("situacaoCompraNome"))
        mode_dispute = self._normalize_text(entry.get("modoDisputaNome") or entry.get("modoDisputa"))
        instrument_type = self._normalize_text(
            entry.get("tipoInstrumentoConvocatorioNome")
            or entry.get("tipoInstrumentoConvocatorio")
        )
        amparo_legal = self._extract_amparo_legal(entry.get("amparoLegal"))
        srp = self._parse_bool_like(entry.get("srp"))
        opening_at = self._normalize_datetime_text(entry.get("dataAberturaProposta"))
        proposal_end_at = self._normalize_datetime_text(entry.get("dataEncerramentoProposta"))
        publication_at = self._normalize_datetime_text(entry.get("dataPublicacaoPncp") or entry.get("dataInclusao"))
        publication_date = publication_at.split("T", 1)[0] if publication_at else None
        estimated_value = self._normalize_float(entry.get("valorTotalEstimado"))
        estimated_value_band = self._classify_estimated_value_band(estimated_value)
        budget_confidential = self._extract_budget_confidential(entry)
        budget_source_count = self._count_budget_sources(entry.get("fontesOrcamentarias"))
        judgment_criterion = self._normalize_text(
            entry.get("criterioJulgamentoNome")
            or entry.get("criterioJulgamento")
        )
        software_classification = self._classify_software_focus(
            object_text=object_text,
            complementary_info=complementary_info,
        )
        proposal_url, proposal_link_type = self._resolve_proposal_link(
            link_processo_eletronico=self._normalize_url(entry.get("linkProcessoEletronico")),
            link_sistema_origem=self._normalize_url(entry.get("linkSistemaOrigem")),
            public_url=public_url,
        )
        closing_window_days = self._calculate_closing_window_days(proposal_end_at)
        buyer_type = self._classify_buyer_type(agency_name)
        region_priority = self._classify_region_priority(
            state=state,
            municipality_ibge=municipality_ibge,
        )
        actionable_now = self._compute_actionable_now(
            proposal_end_at=proposal_end_at,
            proposal_link_type=proposal_link_type,
        )

        title_prefix = " ".join(part for part in [modality_name, notice_number or process_number] if part)
        title = title_prefix if not object_text else f"{title_prefix} - {object_text}" if title_prefix else object_text
        description = self._build_description(
            agency_name=agency_name,
            process_number=process_number,
            status_name=status_name,
            publication_date=publication_date,
            opening_at=opening_at,
            proposal_end_at=proposal_end_at,
            object_text=object_text,
            complementary_info=complementary_info,
            mode_dispute=mode_dispute,
            judgment_criterion=judgment_criterion,
            amparo_legal=amparo_legal,
        )

        auxiliary_links = [
            self._normalize_url(entry.get("linkProcessoEletronico")),
            self._normalize_url(entry.get("linkSistemaOrigem")),
        ]
        links = [link for link in auxiliary_links if link and link != public_url]

        scraped_data = {
            "title": title,
            "description": description,
            "price": estimated_value,
            "currency": "BRL",
            "city": city,
            "state": state,
            "documents": [],
            "links": links,
            "attributes": {
                "agency_name": agency_name,
                "agency_tax_id": agency_tax_id,
                "portal_name": "PNCP",
                "source_record_id": control_number,
                "process_number": process_number,
                "notice_number": notice_number,
                "complementary_info": complementary_info,
                "mode_dispute": mode_dispute,
                "instrument_type": instrument_type,
                "amparo_legal": amparo_legal,
                "modality": modality_name,
                "status": status_name,
                "publication_date": publication_date,
                "opening_at": opening_at,
                "proposal_end_at": proposal_end_at,
                "closing_window_days": closing_window_days,
                "estimated_value": estimated_value,
                "estimated_value_band": estimated_value_band,
                "proposal_url": proposal_url,
                "proposal_link_type": proposal_link_type,
                "actionable_now": actionable_now,
                "buyer_type": buyer_type,
                "region_priority": region_priority,
                "srp": srp,
                "budget_confidential": budget_confidential,
                "budget_source_count": budget_source_count,
                "software_focus": software_classification["software_focus"],
                "software_fit_score": software_classification["software_fit_score"],
                "software_subtype": software_classification["software_subtype"],
                "delivery_model_hint": software_classification["delivery_model_hint"],
                "technology_keywords": software_classification["technology_keywords"],
                "judgment_criterion": judgment_criterion,
                "document_count": 0,
                "dedupe_key": f"pncp:{control_number}",
            },
        }
        return self.build_scraped_item(url=public_url, scraped_data=scraped_data)

    @staticmethod
    def _build_description(
        *,
        agency_name: Optional[str],
        process_number: Optional[str],
        status_name: Optional[str],
        publication_date: Optional[str],
        opening_at: Optional[str],
        proposal_end_at: Optional[str],
        object_text: Optional[str],
        complementary_info: Optional[str],
        mode_dispute: Optional[str],
        judgment_criterion: Optional[str],
        amparo_legal: Optional[str],
    ) -> Optional[str]:
        parts = [
            PNCPLicitacoesScraper._build_sentence("Órgão", agency_name),
            PNCPLicitacoesScraper._build_sentence("Processo", process_number),
            PNCPLicitacoesScraper._build_sentence("Situação", status_name),
            PNCPLicitacoesScraper._build_sentence("Publicação", publication_date),
            PNCPLicitacoesScraper._build_sentence("Abertura", opening_at),
            PNCPLicitacoesScraper._build_sentence("Encerramento das propostas", proposal_end_at),
            PNCPLicitacoesScraper._build_sentence("Modo de disputa", mode_dispute),
            PNCPLicitacoesScraper._build_sentence("Critério de julgamento", judgment_criterion),
            PNCPLicitacoesScraper._build_sentence("Amparo legal", amparo_legal),
            PNCPLicitacoesScraper._build_sentence("Objeto", object_text),
            PNCPLicitacoesScraper._build_sentence("Informações complementares", complementary_info),
        ]
        filtered = [part for part in parts if part]
        fallback_text = complementary_info or object_text
        return " ".join(filtered) if filtered else fallback_text

    @classmethod
    def _build_public_url(cls, control_number: str) -> str:
        parts = cls._parse_control_number(control_number)
        if parts is None:
            return control_number
        cnpj, ano, sequencial = parts
        return cls.PUBLIC_URL_TEMPLATE.format(cnpj=cnpj, ano=ano, sequencial=sequencial)

    @staticmethod
    def _build_sentence(label: str, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        trimmed = value.strip()
        if not trimmed:
            return None
        if trimmed.endswith((".", "!", "?")):
            return f"{label}: {trimmed}"
        return f"{label}: {trimmed}."

    @classmethod
    def _classify_software_focus(
        cls,
        *,
        object_text: Optional[str],
        complementary_info: Optional[str],
    ) -> dict[str, Any]:
        normalized_text = cls._normalize_match_text(" ".join(part for part in [object_text, complementary_info] if part))
        if not normalized_text:
            return {
                "software_focus": False,
                "software_fit_score": 0,
                "software_subtype": None,
                "delivery_model_hint": None,
                "technology_keywords": [],
            }

        matched_keywords: list[str] = []
        total_score = 0
        subtype_scores: dict[str, int] = {}
        delivery_scores: dict[str, int] = {}

        for phrase, weight, subtype, delivery_hint in cls.SOFTWARE_SIGNAL_RULES:
            if phrase in normalized_text:
                matched_keywords.append(phrase.strip())
                total_score += weight
                subtype_scores[subtype] = subtype_scores.get(subtype, 0) + weight
                delivery_scores[delivery_hint] = delivery_scores.get(delivery_hint, 0) + weight

        deduped_keywords: list[str] = []
        seen: set[str] = set()
        for keyword in matched_keywords:
            normalized_keyword = keyword.strip().lower()
            if not normalized_keyword or normalized_keyword in seen:
                continue
            seen.add(normalized_keyword)
            deduped_keywords.append(keyword)

        anti_matches = [phrase for phrase in cls.SOFTWARE_ANTI_PHRASES if phrase in normalized_text]
        penalty = min(60, len(anti_matches) * 20)
        final_score = max(0, min(100, total_score - penalty))
        software_focus = bool(deduped_keywords) and final_score >= cls.SOFTWARE_FOCUS_MIN_SCORE

        software_subtype = None
        if software_focus and subtype_scores:
            software_subtype = max(subtype_scores.items(), key=lambda item: item[1])[0]

        delivery_model_hint = None
        if software_focus and delivery_scores:
            delivery_model_hint = max(delivery_scores.items(), key=lambda item: item[1])[0]

        return {
            "software_focus": software_focus,
            "software_fit_score": final_score,
            "software_subtype": software_subtype,
            "delivery_model_hint": delivery_model_hint,
            "technology_keywords": deduped_keywords if software_focus else [],
        }

    @staticmethod
    def _normalize_match_text(value: str) -> str:
        normalized = unicodedata.normalize("NFD", value or "")
        normalized = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
        normalized = re.sub(r"[^a-zA-Z0-9]+", " ", normalized.lower())
        normalized = " ".join(normalized.split()).strip()
        return f" {normalized} " if normalized else ""

    @classmethod
    def _extract_municipality_ibge(cls, unit: dict[str, Any]) -> Optional[str]:
        if not isinstance(unit, dict):
            return None
        for key, value in unit.items():
            normalized_key = cls._normalize_match_text(str(key)).strip()
            if "ibge" not in normalized_key:
                continue
            digits = re.sub(r"\D", "", str(value or ""))
            if len(digits) == 7:
                return digits
        return None

    @classmethod
    def _extract_amparo_legal(cls, value: Any) -> Optional[str]:
        if isinstance(value, dict):
            for key in ("descricao", "nome", "titulo", "fundamentacao", "amparoLegalDescricao"):
                text = cls._normalize_text(value.get(key))
                if text:
                    return text
        return cls._normalize_text(value)

    @classmethod
    def _parse_bool_like(cls, value: Any) -> Optional[bool]:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        text = cls._normalize_match_text(str(value or "")).strip()
        if not text:
            return None
        if text in {"true", "1", "sim", "s", "ativo", "yes"}:
            return True
        if text in {"false", "0", "nao", "n", "inativo", "no"}:
            return False
        return None

    @classmethod
    def _extract_budget_confidential(cls, entry: dict[str, Any]) -> Optional[bool]:
        direct = cls._parse_bool_like(entry.get("orcamentoSigiloso"))
        if direct is not None:
            return direct
        description = cls._normalize_text(entry.get("orcamentoSigilosoDescricao"))
        if not description:
            return None
        normalized = cls._normalize_match_text(description).strip()
        if normalized in {"sim", "sigiloso", "orcamento sigiloso"}:
            return True
        if normalized in {"nao", "nao sigiloso", "nao se aplica"}:
            return False
        return None

    @staticmethod
    def _count_budget_sources(value: Any) -> Optional[int]:
        if isinstance(value, list):
            return len([item for item in value if item is not None]) or None
        return None

    @staticmethod
    def _resolve_proposal_link(
        *,
        link_processo_eletronico: Optional[str],
        link_sistema_origem: Optional[str],
        public_url: str,
    ) -> tuple[Optional[str], Optional[str]]:
        if link_processo_eletronico:
            return link_processo_eletronico, "processo_eletronico"
        if link_sistema_origem:
            return link_sistema_origem, "sistema_origem"
        return public_url, "pncp"

    def _calculate_closing_window_days(self, proposal_end_at: Optional[str]) -> Optional[int]:
        if not proposal_end_at:
            return None
        parsed = self._parse_datetime(proposal_end_at)
        if parsed is None:
            return None
        delta_seconds = (parsed - self._utc_now()).total_seconds()
        if delta_seconds <= 0:
            return 0
        return max(0, math.ceil(delta_seconds / 86400))

    @staticmethod
    def _classify_estimated_value_band(estimated_value: Optional[float]) -> Optional[str]:
        if not isinstance(estimated_value, (int, float)) or estimated_value <= 0:
            return None
        numeric_value = float(estimated_value)
        if numeric_value <= 100_000:
            return "ate_100k"
        if numeric_value <= 500_000:
            return "100k_500k"
        if numeric_value <= 1_000_000:
            return "500k_1m"
        return "acima_1m"

    @classmethod
    def _classify_buyer_type(cls, agency_name: Optional[str]) -> Optional[str]:
        normalized = cls._normalize_match_text(agency_name or "")
        if not normalized:
            return None
        if any(token in normalized for token in (" camara municipal ", " camara de vereadores ", " camara legislativa ")):
            return "camara"
        if any(token in normalized for token in (" tribunal ", " tj", " trt ", " tre ", " trf ", " ministerio publico ")):
            return "tribunal"
        if any(token in normalized for token in (" universidade ", " instituto federal ", " faculdade ")):
            return "universidade"
        if any(token in normalized for token in (" prefeitura ", " municipio de ")):
            return "prefeitura"
        if any(token in normalized for token in (" governo do estado ", " estado de ", " secretaria de estado ")):
            return "governo_estadual"
        if any(token in normalized for token in (" ministerio ", " uniao ", " presidencia ", " comando do exercito ")):
            return "governo_federal"
        if any(token in normalized for token in (" companhia ", " empresa brasileira ", " empresa municipal ", " sociedade de economia mista ")):
            return "empresa_estatal"
        if any(token in normalized for token in (" autarquia ", " fundo municipal ", " fundacao ")):
            return "autarquia"
        return "outro"

    def _classify_region_priority(
        self,
        *,
        state: Optional[str],
        municipality_ibge: Optional[str],
    ) -> str:
        extra_config = self.config.extra_config if self.config and isinstance(self.config.extra_config, dict) else {}
        target_ufs = set(self._normalize_target_ufs(extra_config.get("target_ufs")))
        target_municipios = set(self._normalize_target_municipios(extra_config.get("target_municipios_ibge")))
        normalized_state = (state or "").strip().upper()

        if municipality_ibge and municipality_ibge in target_municipios:
            return "high"
        if normalized_state and normalized_state in target_ufs:
            return "medium"
        if normalized_state:
            return "low"
        return "unknown"

    def _compute_actionable_now(
        self,
        *,
        proposal_end_at: Optional[str],
        proposal_link_type: Optional[str],
    ) -> bool:
        if proposal_link_type not in {"processo_eletronico", "sistema_origem"}:
            return False
        closing_window_days = self._calculate_closing_window_days(proposal_end_at)
        return closing_window_days is not None and closing_window_days >= 0

    def _is_entry_active(self, entry: dict) -> bool:
        status = self._normalize_text(entry.get("situacaoCompraNome"))
        normalized_status = self._normalize_token(status or "")
        if normalized_status in {
            "suspensa",
            "encerrada",
            "homologada",
            "fracassada",
            "deserta",
            "revogada",
            "anulada",
        }:
            return False

        proposal_end_at = self._parse_datetime(entry.get("dataEncerramentoProposta"))
        if proposal_end_at and proposal_end_at < self._utc_now():
            return False

        return True

    @classmethod
    def _extract_control_number_from_url(cls, url: str) -> Optional[str]:
        if not url:
            return None
        match = cls.CONTROL_NUMBER_PATTERN.search(url)
        if not match:
            return None
        cnpj = match.group("cnpj")
        sequencial = str(int(match.group("sequencial")))
        ano = match.group("ano")
        raw_match = match.group(0)
        middle = raw_match.split("-", 2)[1]
        return f"{cnpj}-{middle}-{int(sequencial):06d}/{ano}"

    @classmethod
    def _extract_detail_parts_from_url(cls, url: str) -> Optional[tuple[str, int, int]]:
        if not url:
            return None
        match = cls.DETAIL_ROUTE_PATTERN.search(url)
        if not match:
            return None
        return (
            match.group("cnpj"),
            int(match.group("ano")),
            int(match.group("sequencial")),
        )

    @classmethod
    def _parse_control_number(cls, control_number: str) -> Optional[tuple[str, int, int]]:
        match = cls.CONTROL_NUMBER_PATTERN.search(control_number or "")
        if not match:
            return None
        return (
            match.group("cnpj"),
            int(match.group("ano")),
            int(match.group("sequencial")),
        )

    @staticmethod
    def _normalize_text(value) -> Optional[str]:
        if value is None:
            return None
        text = html.unescape(str(value))
        text = " ".join(text.split()).strip()
        return text or None

    @staticmethod
    def _normalize_digits(value) -> Optional[str]:
        text = PNCPLicitacoesScraper._normalize_text(value)
        if not text:
            return None
        digits = re.sub(r"\D", "", text)
        return digits or None

    @staticmethod
    def _normalize_float(value) -> Optional[float]:
        if isinstance(value, bool) or value is None:
            return None
        if isinstance(value, (int, float)):
            numeric_value = float(value)
            return numeric_value if numeric_value > 0 else None
        text = PNCPLicitacoesScraper._normalize_text(value)
        if not text:
            return None
        try:
            numeric_value = float(text.replace(".", "").replace(",", "."))
        except ValueError:
            return None
        return numeric_value if numeric_value > 0 else None

    @staticmethod
    def _normalize_datetime_text(value) -> Optional[str]:
        parsed = PNCPLicitacoesScraper._parse_datetime(value)
        if parsed is None:
            return None
        return parsed.replace(microsecond=0).isoformat()

    @staticmethod
    def _parse_datetime(value) -> Optional[datetime]:
        text = PNCPLicitacoesScraper._normalize_text(value)
        if not text:
            return None
        normalized = text.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _normalize_url(value) -> Optional[str]:
        text = PNCPLicitacoesScraper._normalize_text(value)
        if not text:
            return None
        if text.startswith("http://") or text.startswith("https://"):
            return text
        return f"https://{text.lstrip('/')}"

    @staticmethod
    def _safe_int(value) -> Optional[int]:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)
