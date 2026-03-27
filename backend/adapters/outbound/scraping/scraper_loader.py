"""Scraper Loader — registers only job scrapers for kids-jobs."""
import logging

from application.domain.services.scraper_registry import ScraperRegistry

# Jobs
from adapters.outbound.scraping.implementations.jobs.infojobs_scraper import InfoJobsScraper
from adapters.outbound.scraping.implementations.jobs.catho_scraper import CathoScraper
from adapters.outbound.scraping.implementations.jobs.bne_scraper import BNEScraper
from adapters.outbound.scraping.implementations.jobs.nerdin_scraper import NerdinScraper
from adapters.outbound.scraping.implementations.jobs.tractian_scraper import TractianScraper
from adapters.outbound.scraping.implementations.jobs.vanhack_scraper import VanHackScraper
from adapters.outbound.scraping.implementations.jobs.remotar_scraper import RemotarScraper
from adapters.outbound.scraping.implementations.jobs.weworkremotely_scraper import WeWorkRemotelyScraper
from adapters.outbound.scraping.implementations.jobs.remoteok_scraper import RemoteOKScraper
from adapters.outbound.scraping.implementations.jobs.wellfound_scraper import WellfoundScraper
from adapters.outbound.scraping.implementations.jobs.spassu_scraper import SpassuScraper
from adapters.outbound.scraping.implementations.jobs.telegram_jobs_ti_scraper import TelegramJobsTIScraper

logger = logging.getLogger(__name__)


def load_all_scrapers() -> int:
    """
    Load and register all available scrapers.
    Call on application startup.
    """
    scrapers = [
        InfoJobsScraper,
        CathoScraper,
        BNEScraper,
        NerdinScraper,
        TractianScraper,
        VanHackScraper,
        RemotarScraper,
        WeWorkRemotelyScraper,
        RemoteOKScraper,
        WellfoundScraper,
        SpassuScraper,
        TelegramJobsTIScraper,
    ]

    registered_count = 0

    for scraper_class in scrapers:
        try:
            config = scraper_class.get_default_config()
            name = config.metadata.name
            ScraperRegistry.register(name, scraper_class, config)
            registered_count += 1
        except Exception as e:
            logger.error(f"Failed to register scraper {scraper_class.__name__}: {e}")

    logger.info(f"Loaded {registered_count} scrapers into registry")
    return registered_count
