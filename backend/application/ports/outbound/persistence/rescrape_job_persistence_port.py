"""
Rescrape Job Persistence Port
"""
from abc import ABC, abstractmethod
from typing import Optional

from application.domain.entities.rescrape_job import RescrapeJob


class RescrapeJobPersistencePort(ABC):

    @abstractmethod
    def save(self, job: RescrapeJob) -> RescrapeJob:
        ...

    @abstractmethod
    def update(self, job: RescrapeJob) -> RescrapeJob:
        ...

    @abstractmethod
    def find_by_id(self, job_id: int) -> Optional[RescrapeJob]:
        ...

    @abstractmethod
    def find_active_by_source_url(self, source_name: str, url: str) -> Optional[RescrapeJob]:
        ...

    @abstractmethod
    def find_pending(self, limit: int = 10) -> list[RescrapeJob]:
        ...

    @abstractmethod
    def find_all(self, *, status: Optional[str] = None, limit: int = 100, offset: int = 0) -> list[RescrapeJob]:
        ...
