"""
Scraper Configuration Entity
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime

from application.domain.shared.scraper_types import SourceType, ScrapingStrategy


@dataclass
class ScraperMetadata:
    """Metadados do scraper"""
    name: str  # Nome único do scraper (ex: "olx_vehicles")
    display_name: str  # Nome para exibição (ex: "OLX Veículos")
    description: str  # Descrição do que o scraper faz
    category: str  # Categoria principal (real_estate, vehicles, etc.)
    source_type: SourceType  # Tipo de fonte
    author: Optional[str] = None
    version: str = "1.0.0"
    tags: list[str] = field(default_factory=list)  # Tags para busca/filtro


@dataclass
class ScraperConfig:
    """Configuração de um scraper"""
    # Identificação
    metadata: ScraperMetadata

    # Configuração de fonte
    base_url: Optional[str] = None  # URL base para HTTP scrapers
    endpoint: Optional[str] = None  # Endpoint específico

    # Autenticação
    auth_required: bool = False
    credentials: Dict[str, Any] = field(default_factory=dict)  # API keys, tokens, etc.

    # Configurações de comportamento
    enabled: bool = True
    timeout: int = 30  # Timeout em segundos
    max_retries: int = 3
    rate_limit_delay: float = 1.0  # Delay entre requisições (segundos)
    max_items_per_run: Optional[int] = None  # Limite de itens por execução
    strategy: ScrapingStrategy = ScrapingStrategy.HTTP_BASIC
    user_agents: list[str] = field(default_factory=list)

    # Configurações específicas por tipo
    extra_config: Dict[str, Any] = field(default_factory=dict)  # Config específica do tipo

    # Scheduling
    schedule: Optional[str] = None  # Cron expression

    # Metadados de execução
    last_run: Optional[datetime] = None
    last_status: Optional[str] = None
    total_runs: int = 0
    total_items_scraped: int = 0

    def get_full_url(self) -> str:
        """Retorna URL completa"""
        if self.base_url and self.endpoint:
            return f"{self.base_url.rstrip('/')}/{self.endpoint.lstrip('/')}"
        return self.base_url or ""

    def update_stats(self, status: str, items_count: int):
        """Atualiza estatísticas de execução"""
        self.last_run = datetime.utcnow()
        self.last_status = status
        self.total_runs += 1
        self.total_items_scraped += items_count
