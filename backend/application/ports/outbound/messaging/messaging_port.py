"""
Messaging Port - Outbound Port
"""
from abc import ABC, abstractmethod

from application.domain.entities.scraped_item import ScrapedItem


class MessagingPort(ABC):

    @abstractmethod
    def publish(self, item: ScrapedItem, routing_key: str) -> None: ...
