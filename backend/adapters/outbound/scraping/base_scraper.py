"""
Base Scraper — Abstract base for all scrapers (Outbound Adapter)
Provides shared helpers and enforces contract output format.
"""
import html
import logging
import re
import unicodedata
from abc import abstractmethod
from dataclasses import fields
from datetime import datetime
from typing import Optional

from application.domain.entities.scraped_item import Location, ScrapedItem, ScrapedData
from application.domain.entities.scraper_config import ScraperConfig
from application.ports.outbound.scraping.scraper_port import ScraperPort


class BaseScraper(ScraperPort):
    """
    Abstract base class for all scrapers.

    Subclasses MUST implement:
      - scrape() -> list[ScrapedItem]
      - get_default_config() -> ScraperConfig (static)

    Provides:
      - build_scraped_item() — builds ScrapedItem in contract format
      - parse_price()        — shared BRL price parser
      - parse_int()          — extract integer from text
    """
    BRAZIL_UF = {
        "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA",
        "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN",
        "RS", "RO", "RR", "SC", "SP", "SE", "TO",
    }
    BRAZIL_STATE_NAME_TO_UF = {
        "acre": "AC",
        "alagoas": "AL",
        "amapa": "AP",
        "amazonas": "AM",
        "bahia": "BA",
        "ceara": "CE",
        "distrito federal": "DF",
        "espirito santo": "ES",
        "goias": "GO",
        "maranhao": "MA",
        "mato grosso": "MT",
        "mato grosso do sul": "MS",
        "minas gerais": "MG",
        "para": "PA",
        "paraiba": "PB",
        "parana": "PR",
        "pernambuco": "PE",
        "piaui": "PI",
        "rio de janeiro": "RJ",
        "rio grande do norte": "RN",
        "rio grande do sul": "RS",
        "rondonia": "RO",
        "roraima": "RR",
        "santa catarina": "SC",
        "sao paulo": "SP",
        "sergipe": "SE",
        "tocantins": "TO",
    }
    FORBIDDEN_ATTRIBUTE_KEYS = {
        "source",
        "source_platform",
        "platform",
        "location_raw",
        "raw_location",
        "location.raw",
        "location",
    }
    ATTRIBUTE_KEY_ALIASES = {
        "mileage": "mileage_km",
        "discount": "discount_pct",
        "salary_text": "salary_range",
        "salary_period": "salary_type",
        "salary_frequency": "salary_type",
        "salary_unit": "salary_type",
        "salary_interval": "salary_type",
        "area_m2": "total_area_m2",
        "auction_number": "auction_id",
        "leilao_id": "auction_id",
        "leilao_numero": "auction_id",
        "lot": "lot_number",
        "lot_id": "lot_number",
        "lot_code": "lot_number",
        "lote": "lot_number",
        "lote_id": "lot_number",
        "lote_numero": "lot_number",
    }
    ATTR_TYPE_STRING = "string"
    ATTR_TYPE_INT = "int"
    ATTR_TYPE_FLOAT = "float"
    ATTR_TYPE_BOOL = "bool"
    ATTR_TYPE_DATE = "date"
    ATTR_TYPE_DATETIME = "datetime"
    ATTR_TYPE_LIST_STRING = "list_string"
    ATTR_TYPE_ENUM = "enum"
    CATEGORY_ATTRIBUTE_SCHEMA = {
        "vehicles": {
            "year": {"type": ATTR_TYPE_INT, "description": "Ano de fabricação/modelo do veículo."},
            "mileage_km": {"type": ATTR_TYPE_INT, "description": "Quilometragem total do veículo em km."},
            "brand": {"type": ATTR_TYPE_STRING, "description": "Marca do veículo (ex.: Fiat, Toyota)."},
            "model": {"type": ATTR_TYPE_STRING, "description": "Modelo comercial do veículo."},
            "version": {"type": ATTR_TYPE_STRING, "description": "Versão/configuração do modelo."},
            "body_type": {"type": ATTR_TYPE_STRING, "description": "Tipo de carroceria do veículo."},
            "fuel_type": {
                "type": ATTR_TYPE_ENUM,
                "enum": ["gasolina", "etanol", "flex", "diesel", "eletrico", "hibrido", "gnv"],
                "description": "Tipo de combustível predominante.",
            },
            "doors": {"type": ATTR_TYPE_INT, "description": "Quantidade de portas."},
            "color": {"type": ATTR_TYPE_STRING, "description": "Cor predominante do veículo."},
            "engine": {"type": ATTR_TYPE_STRING, "description": "Motorização (ex.: 1.0, 2.0 Turbo)."},
            "features": {
                "type": ATTR_TYPE_LIST_STRING,
                "description": "Lista de itens/opcionais relevantes do veículo.",
            },
            "transmission": {
                "type": ATTR_TYPE_ENUM,
                "enum": ["manual", "automatica", "cvt", "automatizada"],
                "description": "Tipo de câmbio do veículo.",
            },
        },
        "properties": {
            "listing_type": {
                "type": ATTR_TYPE_ENUM,
                "enum": ["sale", "rent", "auction"],
                "description": "Tipo de anúncio imobiliário.",
            },
            "property_type": {
                "type": ATTR_TYPE_ENUM,
                "enum": [
                    "apartamento",
                    "casa",
                    "cobertura",
                    "terreno",
                    "chacara",
                    "sitio",
                    "fazenda",
                    "galpao",
                    "comercial",
                    "rural",
                    "outro",
                ],
                "description": "Tipo do imóvel anunciado.",
            },
            "bedrooms": {"type": ATTR_TYPE_INT, "description": "Quantidade de quartos."},
            "bathrooms": {"type": ATTR_TYPE_INT, "description": "Quantidade de banheiros."},
            "parking_spots": {"type": ATTR_TYPE_INT, "description": "Quantidade de vagas de garagem."},
            "floor": {"type": ATTR_TYPE_INT, "description": "Andar do imóvel, quando aplicável."},
            "total_area_m2": {"type": ATTR_TYPE_FLOAT, "description": "Área total em metros quadrados."},
            "building_area_m2": {
                "type": ATTR_TYPE_FLOAT,
                "description": "Área construída em metros quadrados.",
            },
        },
        "jobs": {
            "company": {"type": ATTR_TYPE_STRING, "description": "Nome da empresa contratante."},
            "country": {"type": ATTR_TYPE_STRING, "description": "País informado para a vaga."},
            "salary_range": {
                "type": ATTR_TYPE_FLOAT,
                "description": "Menor valor numérico identificado para a faixa salarial do anúncio.",
            },
            "salary_type": {
                "type": ATTR_TYPE_ENUM,
                "enum": ["anual", "mensal", "semanal", "diario", "horario", "outro"],
                "description": "Periodicidade da faixa salarial quando inferível do anúncio.",
            },
            "seniority": {
                "type": ATTR_TYPE_ENUM,
                "enum": ["estagio", "junior", "pleno", "senior", "especialista", "lider", "outro"],
                "description": "Nível de senioridade esperado para a vaga.",
            },
            "contract_type": {
                "type": ATTR_TYPE_ENUM,
                "enum": ["clt", "pj", "temporario", "estagio", "freelancer", "cooperado", "aprendiz", "intermitente"],
                "description": "Modelo de contratação da vaga.",
            },
            "work_model": {
                "type": ATTR_TYPE_ENUM,
                "enum": ["presencial", "hibrido", "remoto"],
                "description": "Modelo de trabalho da vaga.",
            },
            "experience_years": {
                "type": ATTR_TYPE_INT,
                "description": "Anos mínimos de experiência requeridos.",
            },
            "telegram_chat": {
                "type": ATTR_TYPE_STRING,
                "description": "Nome do grupo/canal do Telegram de origem.",
            },
            "telegram_chat_id": {
                "type": ATTR_TYPE_STRING,
                "description": "Identificador do chat do Telegram de origem.",
            },
            "telegram_message_id": {
                "type": ATTR_TYPE_INT,
                "description": "ID da mensagem original no Telegram.",
            },
            "telegram_posted_at": {
                "type": ATTR_TYPE_DATETIME,
                "description": "Data/hora original da mensagem no Telegram em ISO.",
            },
            "source_message_type": {
                "type": ATTR_TYPE_ENUM,
                "enum": ["text", "image", "mixed"],
                "description": "Tipo de mensagem de origem no Telegram.",
            },
            "ocr_used": {
                "type": ATTR_TYPE_BOOL,
                "description": "Indica se houve OCR de imagem no post do Telegram.",
            },
            "telegram_public_url": {
                "type": ATTR_TYPE_STRING,
                "description": "Permalink público da mensagem do Telegram, quando disponível.",
            },
            "telegram_canonical_url": {
                "type": ATTR_TYPE_STRING,
                "description": "URL canônica interna da mensagem no formato telegram://chat_id/message_id.",
            },
            "dedupe_key": {
                "type": ATTR_TYPE_STRING,
                "description": "Chave estável usada para deduplicação de vagas originadas do Telegram.",
            },
        },
        "tenders": {
            "agency_name": {
                "type": ATTR_TYPE_STRING,
                "description": "Nome do órgão ou entidade compradora.",
            },
            "agency_tax_id": {
                "type": ATTR_TYPE_STRING,
                "description": "CNPJ do órgão ou entidade compradora.",
            },
            "portal_name": {
                "type": ATTR_TYPE_STRING,
                "description": "Nome do portal oficial de origem da contratação.",
            },
            "source_record_id": {
                "type": ATTR_TYPE_STRING,
                "description": "Identificador oficial do registro na fonte.",
            },
            "process_number": {
                "type": ATTR_TYPE_STRING,
                "description": "Número do processo administrativo/licitatório.",
            },
            "notice_number": {
                "type": ATTR_TYPE_STRING,
                "description": "Número do edital/compra divulgado.",
            },
            "complementary_info": {
                "type": ATTR_TYPE_STRING,
                "description": "Informações complementares textuais da contratação pública.",
            },
            "mode_dispute": {
                "type": ATTR_TYPE_STRING,
                "description": "Modo de disputa informado pela fonte oficial.",
            },
            "instrument_type": {
                "type": ATTR_TYPE_STRING,
                "description": "Tipo do instrumento convocatório da contratação.",
            },
            "amparo_legal": {
                "type": ATTR_TYPE_STRING,
                "description": "Base legal informada pela contratação pública.",
            },
            "modality": {
                "type": ATTR_TYPE_ENUM,
                "enum": [
                    "PREGAO_ELETRONICO",
                    "PREGAO_PRESENCIAL",
                    "CONCORRENCIA",
                    "DISPENSA",
                    "INEXIGIBILIDADE",
                    "LEILAO",
                    "CONCURSO",
                    "CREDENCIAMENTO",
                    "CHAMAMENTO_PUBLICO",
                    "OUTRO",
                ],
                "description": "Modalidade canônica da contratação pública.",
            },
            "status": {
                "type": ATTR_TYPE_ENUM,
                "enum": [
                    "ABERTA",
                    "RECEBENDO_PROPOSTAS",
                    "EM_DISPUTA",
                    "SUSPENSA",
                    "ADIADA",
                    "ENCERRADA",
                    "HOMOLOGADA",
                    "FRACASSADA",
                    "DESERTA",
                    "REVOGADA",
                    "ANULADA",
                ],
                "description": "Status operacional canônico da contratação.",
            },
            "publication_date": {
                "type": ATTR_TYPE_DATE,
                "description": "Data de publicação da contratação no PNCP/portal oficial.",
            },
            "opening_at": {
                "type": ATTR_TYPE_DATETIME,
                "description": "Data/hora de abertura das propostas.",
            },
            "proposal_end_at": {
                "type": ATTR_TYPE_DATETIME,
                "description": "Data/hora final para recebimento de propostas.",
            },
            "closing_window_days": {
                "type": ATTR_TYPE_INT,
                "description": "Quantidade de dias restantes até o fim das propostas.",
            },
            "estimated_value": {
                "type": ATTR_TYPE_FLOAT,
                "description": "Valor total estimado da contratação.",
            },
            "estimated_value_band": {
                "type": ATTR_TYPE_ENUM,
                "enum": ["ate_100k", "100k_500k", "500k_1m", "acima_1m"],
                "description": "Faixa de valor estimado derivada da contratação.",
            },
            "proposal_url": {
                "type": ATTR_TYPE_STRING,
                "description": "Link operacional preferencial para acompanhar/submeter proposta.",
            },
            "proposal_link_type": {
                "type": ATTR_TYPE_ENUM,
                "enum": ["processo_eletronico", "sistema_origem", "pncp"],
                "description": "Tipo do link operacional preferencial da contratação.",
            },
            "actionable_now": {
                "type": ATTR_TYPE_BOOL,
                "description": "Indica se a contratação está operacionalmente acionável agora.",
            },
            "buyer_type": {
                "type": ATTR_TYPE_ENUM,
                "enum": [
                    "prefeitura",
                    "camara",
                    "tribunal",
                    "universidade",
                    "empresa_estatal",
                    "governo_estadual",
                    "governo_federal",
                    "autarquia",
                    "outro",
                ],
                "description": "Tipologia do comprador/órgão derivada do nome oficial.",
            },
            "region_priority": {
                "type": ATTR_TYPE_ENUM,
                "enum": ["high", "medium", "low", "unknown"],
                "description": "Prioridade regional derivada do recorte alvo da source.",
            },
            "srp": {
                "type": ATTR_TYPE_BOOL,
                "description": "Indica se a contratação faz parte de sistema de registro de preços.",
            },
            "budget_confidential": {
                "type": ATTR_TYPE_BOOL,
                "description": "Indica se o orçamento foi marcado como sigiloso.",
            },
            "budget_source_count": {
                "type": ATTR_TYPE_INT,
                "description": "Quantidade de fontes orçamentárias informadas.",
            },
            "software_focus": {
                "type": ATTR_TYPE_BOOL,
                "description": "Indica se a contratação pública tem foco em software/TI aplicacional.",
            },
            "software_fit_score": {
                "type": ATTR_TYPE_INT,
                "description": "Score heurístico de aderência da contratação a software/TI.",
            },
            "software_subtype": {
                "type": ATTR_TYPE_ENUM,
                "enum": [
                    "software_licensing",
                    "software_development",
                    "systems_maintenance",
                    "data_bi",
                    "cloud_infra",
                    "mixed_ti",
                    "other_ti",
                ],
                "description": "Subtipo heurístico de contratação de software/TI.",
            },
            "delivery_model_hint": {
                "type": ATTR_TYPE_ENUM,
                "enum": [
                    "licenca",
                    "implantacao",
                    "sustentacao",
                    "fabrica_software",
                    "servico_continuado",
                    "desenvolvimento",
                    "outro",
                ],
                "description": "Hint operacional do modelo de entrega envolvido na contratação.",
            },
            "technology_keywords": {
                "type": ATTR_TYPE_LIST_STRING,
                "description": "Palavras-chave de software/TI que justificaram a classificação do item.",
            },
            "judgment_criterion": {
                "type": ATTR_TYPE_STRING,
                "description": "Critério de julgamento informado pela fonte, quando disponível.",
            },
            "document_count": {
                "type": ATTR_TYPE_INT,
                "description": "Quantidade de documentos principais associados à contratação.",
            },
            "dedupe_key": {
                "type": ATTR_TYPE_STRING,
                "description": "Chave estável para deduplicação da contratação entre coletas.",
            },
        },
        "auctions": {
            "listing_type": {
                "type": ATTR_TYPE_ENUM,
                "enum": ["auction", "catalog", "direct_sale"],
                "description": "Tipo de listagem dentro do portal de leilão.",
            },
            "auction_id": {"type": ATTR_TYPE_STRING, "description": "Identificador do evento/leilão na origem."},
            "lot_number": {"type": ATTR_TYPE_STRING, "description": "Número público do lote na origem."},
            "auction_code": {"type": ATTR_TYPE_STRING, "description": "Código interno do leilão/lote."},
            "auction_date": {"type": ATTR_TYPE_DATE, "description": "Data principal do leilão (YYYY-MM-DD)."},
            "discount_pct": {
                "type": ATTR_TYPE_FLOAT,
                "description": "Percentual de desconto anunciado para o ativo.",
            },
            "auction_status": {
                "type": ATTR_TYPE_ENUM,
                "enum": ["aberto", "futuro", "encerrado", "suspenso", "cancelado"],
                "description": "Status operacional atual do leilão.",
            },
            "auction_start_at": {
                "type": ATTR_TYPE_DATETIME,
                "description": "Data/hora de início do leilão em formato ISO.",
            },
            "auction_end_at": {
                "type": ATTR_TYPE_DATETIME,
                "description": "Data/hora de encerramento do leilão em formato ISO.",
            },
            "asset_type": {"type": ATTR_TYPE_STRING, "description": "Tipo de ativo leiloado."},
            "appraisal_value": {
                "type": ATTR_TYPE_FLOAT,
                "description": "Valor de avaliação do ativo.",
            },
            "minimum_bid": {"type": ATTR_TYPE_FLOAT, "description": "Lance mínimo exigido no leilão."},
            "current_bid": {"type": ATTR_TYPE_FLOAT, "description": "Maior lance atual registrado."},
            "auctioneer": {"type": ATTR_TYPE_STRING, "description": "Leiloeiro ou casa de leilão responsável."},
        },
        "agribusiness": {
            "listing_type": {
                "type": ATTR_TYPE_ENUM,
                "enum": ["sale", "rent", "auction", "catalog"],
                "description": "Tipo de listagem do item rural.",
            },
            "area_hectares": {"type": ATTR_TYPE_FLOAT, "description": "Área total da propriedade em hectares."},
            "offer_count": {"type": ATTR_TYPE_INT, "description": "Quantidade de ofertas/listagens associadas."},
            "auction_date": {"type": ATTR_TYPE_DATE, "description": "Data de leilão rural (YYYY-MM-DD)."},
            "riverbank": {
                "type": ATTR_TYPE_BOOL,
                "description": "Indica se a área possui margem/acesso a rio.",
            },
            "irrigation": {
                "type": ATTR_TYPE_BOOL,
                "description": "Indica se a propriedade possui sistema de irrigação.",
            },
        },
        "supplements": {
            "supplier_count": {
                "type": ATTR_TYPE_INT,
                "description": "Quantidade de fornecedores identificados para o item.",
            },
            "product_type": {
                "type": ATTR_TYPE_ENUM,
                "enum": ["capsula", "comprimido", "po", "liquido", "goma", "outro"],
                "description": "Tipo/formato principal do suplemento.",
            },
            "package_size": {
                "type": ATTR_TYPE_STRING,
                "description": "Tamanho/apresentação da embalagem (ex.: 60 cápsulas, 1kg).",
            },
            "concentration": {
                "type": ATTR_TYPE_STRING,
                "description": "Concentração declarada do ativo principal.",
            },
            "certifications": {
                "type": ATTR_TYPE_LIST_STRING,
                "description": "Lista de certificações informadas pelo fabricante.",
            },
            "white_label": {
                "type": ATTR_TYPE_BOOL,
                "description": "Indica se o fornecedor oferece produção white label.",
            },
        },
    }
    ENUM_ALIASES = {
        "fuel_type": {
            "gas": "gasolina",
            "gasolina": "gasolina",
            "alcool": "etanol",
            "etanol": "etanol",
            "flex": "flex",
            "diesel": "diesel",
            "eletrico": "eletrico",
            "elétrico": "eletrico",
            "hibrido": "hibrido",
            "híbrido": "hibrido",
            "gnv": "gnv",
        },
        "transmission": {
            "manual": "manual",
            "automatica": "automatica",
            "automático": "automatica",
            "automatico": "automatica",
            "cvt": "cvt",
            "automatizada": "automatizada",
        },
        "work_model": {
            "presencial": "presencial",
            "hibrido": "hibrido",
            "híbrido": "hibrido",
            "remoto": "remoto",
            "home office": "remoto",
        },
        "contract_type": {
            "clt": "clt",
            "pj": "pj",
            "temporario": "temporario",
            "temporário": "temporario",
            "estagio": "estagio",
            "estágio": "estagio",
            "freelancer": "freelancer",
            "cooperado": "cooperado",
            "aprendiz": "aprendiz",
            "intermitente": "intermitente",
        },
        "salary_type": {
            "annual": "anual",
            "annually": "anual",
            "yearly": "anual",
            "anual": "anual",
            "mensal": "mensal",
            "monthly": "mensal",
            "month": "mensal",
            "semanal": "semanal",
            "weekly": "semanal",
            "week": "semanal",
            "diario": "diario",
            "diária": "diario",
            "diario(a)": "diario",
            "daily": "diario",
            "day": "diario",
            "horario": "horario",
            "hourly": "horario",
            "hour": "horario",
            "hora": "horario",
            "outro": "outro",
        },
        "modality": {
            "pregao eletronico": "pregao_eletronico",
            "pregao - eletronico": "pregao_eletronico",
            "pregao eletrônico": "pregao_eletronico",
            "pregao - eletrônico": "pregao_eletronico",
            "pregao presencial": "pregao_presencial",
            "pregão presencial": "pregao_presencial",
            "concorrencia": "concorrencia",
            "concorrência": "concorrencia",
            "dispensa": "dispensa",
            "inexigibilidade": "inexigibilidade",
            "leilao": "leilao",
            "leilão": "leilao",
            "concurso": "concurso",
            "credenciamento": "credenciamento",
            "chamamento publico": "chamamento_publico",
            "chamamento público": "chamamento_publico",
        },
        "status": {
            "aberta": "aberta",
            "aberto": "aberta",
            "divulgada no pncp": "aberta",
            "recebendo proposta": "recebendo_propostas",
            "recebendo propostas": "recebendo_propostas",
            "em disputa": "em_disputa",
            "suspensa": "suspensa",
            "adiada": "adiada",
            "encerrada": "encerrada",
            "homologada": "homologada",
            "fracassada": "fracassada",
            "deserta": "deserta",
            "revogada": "revogada",
            "anulada": "anulada",
        },
        "listing_type": {
            "auction": "auction",
            "leilao": "auction",
            "leilão": "auction",
            "catalog": "catalog",
            "catalogo": "catalog",
            "catálogo": "catalog",
            "direct sale": "direct_sale",
            "direct_sale": "direct_sale",
            "venda direta": "direct_sale",
            "compre agora": "direct_sale",
            "proposta": "direct_sale",
        },
        "auction_status": {
            "aberto": "aberto",
            "aberta": "aberto",
            "aberto para lances": "aberto",
            "em andamento": "aberto",
            "andamento": "aberto",
            "futuro": "futuro",
            "agendado": "futuro",
            "proximo": "futuro",
            "próximo": "futuro",
            "encerrado": "encerrado",
            "encerrada": "encerrado",
            "finalizado": "encerrado",
            "finalizada": "encerrado",
            "arrematado": "encerrado",
            "vendido": "encerrado",
            "suspenso": "suspenso",
            "suspensa": "suspenso",
            "cancelado": "cancelado",
            "cancelada": "cancelado",
        },
    }

    def __init__(self, config: Optional[ScraperConfig] = None):
        self.config = config or self.get_default_config()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.last_scrape_url_diagnostics: dict[str, Optional[str] | bool] = {
            "missing": False,
            "reason": None,
            "url": None,
        }

    @staticmethod
    @abstractmethod
    def get_default_config() -> ScraperConfig:
        """Return default configuration for this scraper"""
        ...

    @abstractmethod
    def scrape(self) -> list[ScrapedItem]:
        """Execute scraping and return items in contract format"""
        ...

    def scrape_url(self, url: str) -> Optional[ScrapedItem]:
        """
        Default single-item scraping entrypoint for queue-based rescrape.

        Fallback strategy:
        1. Execute `scrape()` normally.
        2. Return the first item whose canonical URL matches the requested URL.

        Scrapers with a dedicated detail page SHOULD override this method to avoid
        depending on the listing page and to make rescrape deterministic.
        """
        normalized_target_url = self._normalize_scrape_url(url)
        self._reset_scrape_url_diagnostics(url=normalized_target_url or url)
        if not normalized_target_url:
            return None

        try:
            for item in self.scrape():
                normalized_item_url = self._normalize_scrape_url(getattr(item, "url", None))
                if normalized_item_url == normalized_target_url:
                    return item
        except Exception:
            self.logger.exception("Fallback scrape_url failed for %s", normalized_target_url)
            raise

        return None

    def _reset_scrape_url_diagnostics(self, *, url: Optional[str] = None) -> None:
        self.last_scrape_url_diagnostics = {
            "missing": False,
            "reason": None,
            "url": url,
        }

    def _mark_scrape_url_missing(self, *, reason: str, url: Optional[str] = None) -> None:
        self.last_scrape_url_diagnostics = {
            "missing": True,
            "reason": (reason or "").strip() or None,
            "url": url,
        }

    # === ScraperPort interface ===

    def get_name(self) -> str:
        return self.config.metadata.name

    def is_enabled(self) -> bool:
        return self.config.enabled if self.config else True

    def get_config(self) -> Optional[ScraperConfig]:
        return self.config

    # === Shared helpers ===

    def build_scraped_item(
        self,
        url: str,
        scraped_data: ScrapedData | dict | None,
    ) -> ScrapedItem:
        """
        Build a ScrapedItem that conforms to the contract.

        Args:
            url:               URL of the listing
            scraped_data:      ScrapedData with title, description, price, etc.
        """
        category = self.config.metadata.category if self.config and self.config.metadata else None
        normalized_scraped_data = self._normalize_scraped_data(scraped_data, category=category)
        meta = self.config.metadata
        return ScrapedItem(
            url=url,
            source_name=meta.name,
            category_name=meta.category,
            scraped_data=normalized_scraped_data,
        )

    @staticmethod
    def _normalize_scrape_url(value: Optional[str]) -> str:
        normalized = (value or "").strip()
        if not normalized:
            return ""
        return normalized.split("#", 1)[0].rstrip("/")

    @staticmethod
    def _normalize_scraped_data(
        scraped_data: ScrapedData | dict | None,
        *,
        category: Optional[str] = None,
    ) -> ScrapedData:
        """
        Normalize dict payloads to ScrapedData.

        This keeps backward compatibility with older scrapers that still build
        `scraped_data` as dict.
        """
        payload = BaseScraper._to_payload_dict(scraped_data)
        if payload is None:
            return ScrapedData()
        category_key = (category or "").strip().lower()

        attributes = payload.get("attributes")
        if not isinstance(attributes, dict):
            attributes = {}
        else:
            attributes = dict(attributes)

        location_value = payload.get("location")
        normalized_location = None
        if isinstance(location_value, Location):
            normalized_location = location_value
        elif isinstance(location_value, dict):
            latitude = location_value.get("latitude")
            longitude = location_value.get("longitude")
            if latitude is not None or longitude is not None:
                normalized_location = Location(latitude=latitude, longitude=longitude)

        raw_location_hints: list[str] = []
        extracted_raw_location = BaseScraper._extract_raw_location(location_value)
        if extracted_raw_location:
            raw_location_hints.append(extracted_raw_location)

        raw_location_from_attributes = BaseScraper._extract_raw_location_from_attributes(attributes)
        if raw_location_from_attributes:
            raw_location_hints.append(raw_location_from_attributes)

        attributes = BaseScraper._normalize_attributes(attributes, category=category)
        raw_location_hint = next((value for value in raw_location_hints if value), None)

        allowed_fields = {field.name for field in fields(ScrapedData)}
        normalized_payload = {}
        for key, value in payload.items():
            if key in {"location", "attributes"}:
                continue
            if key in allowed_fields:
                normalized_payload[key] = value

        normalized_payload["title"] = BaseScraper._normalize_title_text(
            normalized_payload.get("title")
        )
        normalized_payload["description"] = BaseScraper._normalize_description_text(
            normalized_payload.get("description")
        )
        if category_key == "jobs":
            normalized_payload["title"] = BaseScraper._normalize_job_title(
                normalized_payload.get("title")
            )

        city_value = BaseScraper._normalize_optional_text(normalized_payload.get("city"))
        state_value = BaseScraper._normalize_state_value(normalized_payload.get("state"))

        if raw_location_hint and (not city_value or not state_value):
            city_guess, state_guess = BaseScraper._extract_city_state_pair(raw_location_hint)
            if not city_value and city_guess:
                city_value = city_guess
            if not state_value and state_guess:
                state_value = state_guess

        normalized_payload["city"] = city_value
        normalized_payload["state"] = state_value
        if (
            category_key == "jobs"
            and not isinstance(normalized_payload.get("price"), bool)
            and normalized_payload.get("price") is None
        ):
            salary_floor = attributes.get("salary_range")
            if isinstance(salary_floor, (int, float)) and salary_floor > 0:
                normalized_payload["price"] = float(salary_floor)
        normalized_payload["location"] = normalized_location
        normalized_payload["attributes"] = attributes
        return ScrapedData(**normalized_payload)

    @staticmethod
    def _normalize_job_title(value: Optional[str]) -> Optional[str]:
        normalized = BaseScraper._normalize_title_text(value)
        if not normalized:
            return None
        return normalized[:1].upper() + normalized[1:]

    @staticmethod
    def _normalize_title_text(value) -> Optional[str]:
        normalized = BaseScraper._normalize_optional_text(value)
        if not normalized:
            return None
        return BaseScraper._replace_dash_variants(normalized)

    @staticmethod
    def _to_payload_dict(scraped_data: ScrapedData | dict | None) -> Optional[dict]:
        if isinstance(scraped_data, ScrapedData):
            payload = {field.name: getattr(scraped_data, field.name) for field in fields(ScrapedData)}
            payload["attributes"] = dict(scraped_data.attributes or {})
            payload["images"] = list(scraped_data.images or [])
            payload["videos"] = list(scraped_data.videos or [])
            payload["documents"] = list(scraped_data.documents or [])
            payload["links"] = list(scraped_data.links or [])
            return payload
        if isinstance(scraped_data, dict):
            return dict(scraped_data)
        return None

    @staticmethod
    def _extract_raw_location(location_value) -> Optional[str]:
        if isinstance(location_value, str):
            raw = location_value.strip()
            return raw or None
        if isinstance(location_value, dict):
            for key in ("raw", "name", "label"):
                value = location_value.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return None

    @staticmethod
    def _extract_raw_location_from_attributes(attributes: dict) -> Optional[str]:
        for key, value in attributes.items():
            normalized_key = str(key).strip().lower()
            if normalized_key in {"location_raw", "raw_location", "location.raw"}:
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return None

    @staticmethod
    def _normalize_attributes(attributes: dict, *, category: Optional[str]) -> dict:
        normalized: dict = {}
        category_key = (category or "").strip().lower()
        schema = BaseScraper.CATEGORY_ATTRIBUTE_SCHEMA.get(category_key, {})

        for key, value in attributes.items():
            normalized_key = str(key).strip().lower()
            if not normalized_key or normalized_key in BaseScraper.FORBIDDEN_ATTRIBUTE_KEYS:
                continue

            canonical_key = BaseScraper.ATTRIBUTE_KEY_ALIASES.get(normalized_key, normalized_key)
            field_schema = schema.get(canonical_key)
            if field_schema is None:
                continue

            normalized_value = BaseScraper._normalize_attribute_value(canonical_key, value, field_schema)
            if normalized_value is None:
                continue
            normalized[canonical_key] = normalized_value

        if category_key == "jobs":
            BaseScraper._enrich_job_salary_attributes(source_attributes=attributes, normalized_attributes=normalized)

        return normalized

    @staticmethod
    def _normalize_attribute_value(key: str, value, field_schema: dict):
        if value is None:
            return None

        if key == "salary_range":
            return BaseScraper._normalize_salary_range_value(value)

        field_type = field_schema.get("type", BaseScraper.ATTR_TYPE_STRING)
        if field_type == BaseScraper.ATTR_TYPE_STRING:
            return BaseScraper._normalize_optional_text(value)
        if field_type == BaseScraper.ATTR_TYPE_INT:
            if key == "year":
                return BaseScraper._parse_year_value(value)
            return BaseScraper._parse_int_value(value)
        if field_type == BaseScraper.ATTR_TYPE_FLOAT:
            return BaseScraper._parse_float_value(value)
        if field_type == BaseScraper.ATTR_TYPE_BOOL:
            return BaseScraper._parse_bool_value(value)
        if field_type == BaseScraper.ATTR_TYPE_DATE:
            return BaseScraper._normalize_date_value(value)
        if field_type == BaseScraper.ATTR_TYPE_DATETIME:
            return BaseScraper._normalize_datetime_value(value)
        if field_type == BaseScraper.ATTR_TYPE_LIST_STRING:
            return BaseScraper._normalize_string_list(value)
        if field_type == BaseScraper.ATTR_TYPE_ENUM:
            return BaseScraper._normalize_enum_value(
                key=key,
                value=value,
                allowed_values=field_schema.get("enum", []),
            )
        return None

    @staticmethod
    def _parse_year_value(value) -> Optional[int]:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            year_match = re.search(r"\b(19|20)\d{2}\b", value)
            if year_match:
                return int(year_match.group(0))
            digits = "".join(ch for ch in value if ch.isdigit())
            if len(digits) == 4:
                return int(digits)
        return None

    @staticmethod
    def _parse_int_value(value) -> Optional[int]:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            digits = "".join(ch for ch in value if ch.isdigit())
            if digits:
                return int(digits)
        return None

    @staticmethod
    def _parse_float_value(value) -> Optional[float]:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if not isinstance(value, str):
            return None

        raw = value.strip()
        if not raw:
            return None
        match = re.search(r"-?\d{1,3}(?:\.\d{3})*(?:,\d+)?|-?\d+(?:,\d+)?|-?\d+(?:\.\d+)?", raw)
        if not match:
            return None
        number_token = match.group(0)

        if "," in number_token and "." in number_token:
            normalized = number_token.replace(".", "").replace(",", ".")
        elif "," in number_token:
            normalized = number_token.replace(",", ".")
        else:
            normalized = number_token
        try:
            return float(normalized)
        except ValueError:
            return None

    @staticmethod
    def _parse_bool_value(value) -> Optional[bool]:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if not isinstance(value, str):
            return None
        normalized = BaseScraper._normalize_token(value)
        if normalized in {"1", "true", "sim", "yes", "y", "ativo"}:
            return True
        if normalized in {"0", "false", "nao", "não", "no", "n", "inativo"}:
            return False
        return None

    @staticmethod
    def _normalize_date_value(value) -> Optional[str]:
        if isinstance(value, datetime):
            return value.date().isoformat()
        if not isinstance(value, str):
            return None
        raw = value.strip()
        if not raw:
            return None
        try:
            normalized = raw.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized)
            return parsed.date().isoformat()
        except ValueError:
            pass
        for fmt in (
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%d/%m/%y",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%d/%m/%y %H:%M:%S",
            "%d/%m/%y %H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
        ):
            try:
                return datetime.strptime(raw, fmt).date().isoformat()
            except ValueError:
                continue
        return None

    @staticmethod
    def _normalize_datetime_value(value) -> Optional[str]:
        if isinstance(value, datetime):
            return value.replace(microsecond=0).isoformat()
        if not isinstance(value, str):
            return None
        raw = value.strip()
        if not raw:
            return None

        try:
            normalized = raw.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized)
            return parsed.replace(microsecond=0).isoformat()
        except ValueError:
            pass

        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%d/%m/%y %H:%M:%S",
            "%d/%m/%y %H:%M",
            "%d-%m-%Y %H:%M:%S",
            "%d-%m-%Y %H:%M",
        ):
            try:
                parsed = datetime.strptime(raw, fmt)
                return parsed.replace(microsecond=0).isoformat()
            except ValueError:
                continue
        return None

    @staticmethod
    def _normalize_string_list(value) -> Optional[list[str]]:
        items: list[str] = []
        if isinstance(value, str):
            raw_tokens = re.split(r"[;,|]", value)
            items = [token for token in raw_tokens]
        elif isinstance(value, (list, tuple, set)):
            items = [str(item) for item in value]
        else:
            return None

        normalized: list[str] = []
        seen: set[str] = set()
        for item in items:
            text = BaseScraper._normalize_optional_text(item)
            if not text:
                continue
            key = BaseScraper._normalize_token(text)
            if key in seen:
                continue
            seen.add(key)
            normalized.append(text)

        return normalized or None

    @staticmethod
    def _normalize_enum_value(*, key: str, value, allowed_values: list[str]) -> Optional[str]:
        text = BaseScraper._normalize_optional_text(value)
        if not text:
            return None

        aliases = BaseScraper.ENUM_ALIASES.get(key, {})
        token = BaseScraper._normalize_token(text)
        token = aliases.get(token, token)
        token = BaseScraper._normalize_token(token)

        allowed_map = {BaseScraper._normalize_token(item): item for item in allowed_values}
        return allowed_map.get(token)

    @staticmethod
    def _enrich_job_salary_attributes(*, source_attributes: dict, normalized_attributes: dict) -> None:
        if "salary_type" in normalized_attributes:
            return

        for key, value in source_attributes.items():
            normalized_key = str(key).strip().lower()
            canonical_key = BaseScraper.ATTRIBUTE_KEY_ALIASES.get(normalized_key, normalized_key)
            if canonical_key != "salary_range":
                continue
            detected_salary_type = BaseScraper._detect_salary_type(value)
            if detected_salary_type:
                normalized_attributes["salary_type"] = detected_salary_type
                return

    @staticmethod
    def _normalize_salary_range_value(value) -> Optional[float]:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            numeric_value = float(value)
            return numeric_value if numeric_value > 0 else None
        if not isinstance(value, str):
            return None

        raw_text = value.strip()
        if not raw_text:
            return None

        amounts = BaseScraper._extract_salary_amounts(raw_text)
        if not amounts:
            return None

        for amount in amounts:
            if amount > 0:
                return float(amount)
        return None

    @staticmethod
    def _extract_salary_amounts(value: str) -> list[float]:
        matches: list[float] = []
        pattern = re.compile(
            r"(?<![A-Za-z0-9])(?:r\$\s*|us\$\s*|\$\s*|usd\s*|brl\s*|eur\s*|gbp\s*)?(\d[\d.,]*)(?:\s*([kKmM]))?(?![A-Za-z0-9])"
        )
        for match in pattern.finditer(value):
            amount = BaseScraper._parse_salary_amount_token(match.group(1), suffix=match.group(2))
            if amount is None or amount <= 0:
                continue
            matches.append(float(amount))
        return matches

    @staticmethod
    def _parse_salary_amount_token(token: str, *, suffix: Optional[str] = None) -> Optional[float]:
        raw = re.sub(r"[^\d,.\-]", "", token or "").strip()
        if not raw or raw in {"-", ".", ","}:
            return None

        normalized = raw
        if "," in raw and "." in raw:
            last_comma = raw.rfind(",")
            last_dot = raw.rfind(".")
            if last_comma > last_dot:
                decimal_digits = len(raw[last_comma + 1 :])
                normalized = raw.replace(".", "").replace(",", ".") if decimal_digits in {1, 2} else raw.replace(".", "").replace(",", "")
            else:
                decimal_digits = len(raw[last_dot + 1 :])
                normalized = raw.replace(",", "") if decimal_digits in {1, 2} else raw.replace(",", "").replace(".", "")
        elif "," in raw:
            decimal_digits = len(raw.split(",")[-1])
            normalized = raw.replace(",", ".") if decimal_digits in {1, 2} else raw.replace(",", "")
        elif "." in raw:
            decimal_digits = len(raw.split(".")[-1])
            normalized = raw if decimal_digits in {1, 2} else raw.replace(".", "")

        try:
            amount = float(normalized)
        except ValueError:
            return None

        suffix_token = (suffix or "").strip().lower()
        if suffix_token == "k":
            amount *= 1_000
        elif suffix_token == "m":
            amount *= 1_000_000
        return amount

    @staticmethod
    def _detect_salary_type(value) -> Optional[str]:
        if not isinstance(value, str):
            return None

        text = BaseScraper._normalize_ascii_text(value).lower()
        salary_type_patterns = {
            "anual": (r"\bannual\b", r"\bannually\b", r"\byearly\b", r"\banual\b", r"/annual\b", r"/year\b", r"/yr\b", r"\bper year\b", r"\bpor ano\b", r"\bao ano\b"),
            "mensal": (r"\bmonthly\b", r"\bmensal\b", r"/month\b", r"/mo\b", r"\bper month\b", r"\bpor mes\b", r"\bao mes\b"),
            "semanal": (r"\bweekly\b", r"\bsemanal\b", r"/week\b", r"/wk\b", r"\bper week\b", r"\bpor semana\b"),
            "diario": (r"\bdaily\b", r"\bdiario\b", r"/day\b", r"\bper day\b", r"\bpor dia\b", r"\bao dia\b"),
            "horario": (r"\bhourly\b", r"\bhorario\b", r"/hour\b", r"/hr\b", r"\bper hour\b", r"\bpor hora\b", r"\ba hora\b"),
        }
        for salary_type, patterns in salary_type_patterns.items():
            if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns):
                return salary_type
        return None

    @staticmethod
    def _normalize_optional_text(value) -> Optional[str]:
        if not isinstance(value, str):
            return None
        text = " ".join(value.split()).strip()
        return text or None

    @staticmethod
    def _normalize_description_text(value) -> Optional[str]:
        if not isinstance(value, str):
            return None

        text = html.unescape(value)
        text = re.sub(r"[\u00a0\u1680\u2000-\u200f\u2028\u2029\u202f\u205f\u3000]", " ", text)
        text = BaseScraper._replace_dash_variants(text)
        text = text.replace("?", "")
        text = text.replace("\t", " ")
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        # Remove tags HTML e preserva separação mínima entre blocos.
        text = re.sub(r"<\s*br\s*/?\s*>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(
            r"</?(?:p|div|li|ul|ol|strong|b|em|span|h[1-6]|section|article|header|footer|table|tr|td)\b[^>]*>",
            " ",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"[ ]{2,}", " ", text)
        text = re.sub(r" *\n+ *", "\n", text)
        text = re.sub(r"\n{2,}", "\n", text)
        text = text.replace("\n", " ")
        text = re.sub(r"\s{2,}", " ", text).strip()
        return text or None

    @staticmethod
    def _replace_dash_variants(value: str) -> str:
        return value.replace("—", "-").replace("–", "-")

    @staticmethod
    def compute_discount_pct(reference_value: Optional[float], discounted_value: Optional[float]) -> Optional[float]:
        if reference_value is None or discounted_value is None:
            return None
        if reference_value <= 0 or discounted_value < 0:
            return None
        if discounted_value > reference_value:
            return None
        return round(((reference_value - discounted_value) / reference_value) * 100.0, 2)

    @staticmethod
    def _normalize_token(value: str) -> str:
        ascii_value = BaseScraper._normalize_ascii_text(value).lower()
        ascii_value = re.sub(r"[^a-z0-9\s]", " ", ascii_value)
        ascii_value = re.sub(r"\s{2,}", " ", ascii_value).strip()
        return ascii_value

    @staticmethod
    def _normalize_state_value(value) -> Optional[str]:
        if not isinstance(value, str):
            return None

        text = " ".join(value.split()).strip()
        if not text:
            return None

        uf_candidate = BaseScraper._extract_state_from_text(text)
        if uf_candidate:
            return uf_candidate
        return None

    @staticmethod
    def _normalize_ascii_text(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value)
        return "".join(ch for ch in normalized if not unicodedata.combining(ch))

    @staticmethod
    def _extract_city_state_pair(raw_text: Optional[str]) -> tuple[Optional[str], Optional[str]]:
        if not isinstance(raw_text, str):
            return None, None

        text = " ".join(raw_text.split())
        if not text:
            return None, None

        for match in re.finditer(
            r"(?:\bem\s+)?([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'`\-\s]{1,60})\s*[-/,]\s*([A-Za-z]{2})\b",
            text,
            flags=re.IGNORECASE,
        ):
            city_candidate = re.sub(r"\s{2,}", " ", match.group(1)).strip(" -/,")
            state_candidate = match.group(2).upper()
            if state_candidate not in BaseScraper.BRAZIL_UF:
                continue
            if not city_candidate:
                continue
            return city_candidate.title(), state_candidate

        state_fallback = BaseScraper._extract_state_from_text(text)
        if state_fallback:
            return None, state_fallback
        return None, None

    @staticmethod
    def _extract_state_from_text(text: str) -> Optional[str]:
        for token in re.findall(r"\b([A-Za-z]{2})\b", text):
            state_candidate = token.upper()
            if state_candidate in BaseScraper.BRAZIL_UF:
                return state_candidate

        normalized_text = BaseScraper._normalize_ascii_text(text).lower()
        normalized_text = re.sub(r"[^a-z0-9\s]", " ", normalized_text)
        normalized_text = re.sub(r"\s{2,}", " ", normalized_text).strip()
        for state_name, state_uf in BaseScraper.BRAZIL_STATE_NAME_TO_UF.items():
            if re.search(rf"\b{re.escape(state_name)}\b", normalized_text):
                return state_uf
        return None

    @staticmethod
    def parse_price(price_text: Optional[str]) -> Optional[float]:
        """Parse Brazilian price string (R$ 1.234,56) to float"""
        if not price_text:
            return None
        lower = price_text.lower().strip()
        if lower in ("sob consulta", "a combinar", "consulte", "grátis", ""):
            return None
        try:
            cleaned = price_text.replace("R$", "").replace(".", "").replace(",", ".").strip()
            return float(cleaned)
        except (ValueError, AttributeError):
            return None

    @staticmethod
    def parse_int(text: Optional[str]) -> Optional[int]:
        """Extract first integer from a text string"""
        if not text:
            return None
        try:
            digits = "".join(filter(str.isdigit, text))
            return int(digits) if digits else None
        except ValueError:
            return None

    @staticmethod
    def extract_coordinates_from_google_maps_text(text: Optional[str]) -> tuple[Optional[float], Optional[float]]:
        """
        Extract (latitude, longitude) from Google Maps URLs/snippets found in text.
        Supports patterns like:
        - .../@-22.88,-48.44,17z
        - ...?q=-22.88,-48.44
        - ...?query=loc:-22.88,-48.44
        - ...!3d-22.88!4d-48.44
        """
        if not isinstance(text, str) or not text.strip():
            return None, None

        normalized = text
        normalized = normalized.replace("\\u0026", "&").replace("&amp;", "&")
        normalized = normalized.replace("\\/", "/")

        patterns = [
            r"@(-?\d{1,3}\.\d+),(-?\d{1,3}\.\d+)",
            r"!3d(-?\d{1,3}\.\d+)!4d(-?\d{1,3}\.\d+)",
            r"[?&](?:q|query|ll|center)=(?:loc:)?(-?\d{1,3}\.\d+),(-?\d{1,3}\.\d+)",
            r"/maps/search/(?:loc:)?(-?\d{1,3}\.\d+),(-?\d{1,3}\.\d+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, normalized, flags=re.IGNORECASE)
            if not match:
                continue
            try:
                latitude = float(match.group(1))
                longitude = float(match.group(2))
            except (TypeError, ValueError):
                continue
            if BaseScraper._is_valid_lat_lon(latitude, longitude):
                return latitude, longitude

        return None, None

    @staticmethod
    def _is_valid_lat_lon(latitude: float, longitude: float) -> bool:
        return -90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0

    def get_metadata(self) -> dict:
        """Return scraper metadata as dict"""
        if self.config and self.config.metadata:
            return {
                "name": self.config.metadata.name,
                "display_name": self.config.metadata.display_name,
                "description": self.config.metadata.description,
                "category": self.config.metadata.category,
                "source_type": self.config.metadata.source_type.value,
                "version": self.config.metadata.version,
                "enabled": self.config.enabled,
            }
        return {"name": self.__class__.__name__, "enabled": True}
