"""
Scraper Types and Enums
"""
from enum import Enum


class SourceType(str, Enum):
    """Como o scraper coleta dados"""
    HTTP = "http"
    TELEGRAM = "telegram"
    API = "api"
    RSS = "rss"
    WEBSOCKET = "websocket"
    SELENIUM = "selenium"
    WEBHOOK = "webhook"
    DATABASE = "database"
    FILE = "file"

    @classmethod
    def values(cls):
        return [member.value for member in cls]


class ScrapingCategory(str, Enum):
    """O que está sendo coletado"""
    VEHICLES = "vehicles"
    PROPERTIES = "properties"
    AGRIBUSINESS = "agribusiness"
    AUCTIONS = "auctions"
    JOBS = "jobs"
    TENDERS = "tenders"
    SUPPLEMENTS = "supplements"
    TRAVEL = "travel"
    GENERAL = "general"

    @classmethod
    def values(cls):
        return [member.value for member in cls]


class ScraperStatus(str, Enum):
    """Status de execução do scraper"""
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    DISABLED = "disabled"


class ScrapingStrategy(str, Enum):
    """Estratégia de coleta para scrapers HTTP/browser"""
    HTTP_BASIC = "http_basic"
    HTTP_ANTIBOT = "http_antibot"
    BROWSER_PLAYWRIGHT = "browser_playwright"

    @classmethod
    def values(cls):
        return [member.value for member in cls]
