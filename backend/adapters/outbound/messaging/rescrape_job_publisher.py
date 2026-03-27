"""
RabbitMQ publisher for rescrape jobs.
"""
from __future__ import annotations

import json
from typing import Callable, Optional

import pika


class RescrapeJobPublisher:
    def __init__(
        self,
        connection: Optional[pika.BlockingConnection] = None,
        queue_name: str = "hunt-scraping-rescrape",
        connection_factory: Optional[Callable[[], pika.BlockingConnection]] = None,
    ):
        self.connection = connection
        self._connection_factory = connection_factory
        self.queue_name = queue_name
        self.channel = self.connection.channel() if self.connection else None

    def _ensure_channel(self) -> None:
        if self.connection and not self.connection.is_closed and self.channel and self.channel.is_open:
            return

        if not self.connection or self.connection.is_closed:
            if not self._connection_factory:
                raise RuntimeError("RabbitMQ connection is closed and no factory is available to reconnect.")
            self.connection = self._connection_factory()
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue=self.queue_name, durable=True)

    def _reset_connection(self) -> None:
        if self.connection and not self.connection.is_closed:
            try:
                self.connection.close()
            except Exception:
                pass
        self.connection = None
        self.channel = None

    def publish(self, job_id: int) -> None:
        payload = json.dumps({"job_id": job_id})
        last_error: Optional[Exception] = None

        for _ in range(2):
            try:
                self._ensure_channel()
                assert self.channel is not None
                self.channel.basic_publish(
                    exchange="",
                    routing_key=self.queue_name,
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

        raise RuntimeError(f"Error publishing rescrape job to RabbitMQ: {last_error}") from last_error

    def close(self) -> None:
        self._reset_connection()
