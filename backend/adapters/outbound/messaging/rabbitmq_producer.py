"""
RabbitMQ Producer - Outbound Adapter
"""
import json
from typing import Callable, Optional

import pika

from application.domain.entities.scraped_item import ScrapedItem
from application.domain.exceptions.domain_exceptions import PublishException
from application.ports.outbound.messaging.messaging_port import MessagingPort


class RabbitMQProducer(MessagingPort):

    def __init__(
        self,
        connection: Optional[pika.BlockingConnection] = None,
        exchange_name: str = "hunt.scraping",
        connection_factory: Optional[Callable[[], pika.BlockingConnection]] = None,
    ):
        self.connection = connection
        self._connection_factory = connection_factory
        self.exchange_name = exchange_name
        self.channel = self.connection.channel() if self.connection else None

    def _ensure_channel(self) -> None:
        if (
            self.connection
            and not self.connection.is_closed
            and self.channel
            and self.channel.is_open
        ):
            return

        if not self.connection or self.connection.is_closed:
            if not self._connection_factory:
                raise PublishException("RabbitMQ connection is closed and no factory is available to reconnect.")
            self.connection = self._connection_factory()
        self.channel = self.connection.channel()

    def _reset_connection(self) -> None:
        if self.connection and not self.connection.is_closed:
            try:
                self.connection.close()
            except Exception:
                pass
        self.connection = None
        self.channel = None

    def publish(self, item: ScrapedItem, routing_key: str) -> None:
        payload = json.dumps(item.to_dict())
        last_error: Optional[Exception] = None
        for _ in range(2):
            try:
                self._ensure_channel()
                assert self.channel is not None
                self.channel.basic_publish(
                    exchange=self.exchange_name,
                    routing_key=routing_key,
                    body=payload,
                    properties=pika.BasicProperties(
                        delivery_mode=2,
                        content_type="application/json",
                    ),
                )
                return
            except Exception as exc:
                last_error = exc
                self._reset_connection()
                continue

        raise PublishException(f"Error publishing to RabbitMQ: {last_error}") from last_error

    def close(self):
        self._reset_connection()
