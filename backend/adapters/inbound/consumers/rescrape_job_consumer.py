"""
RabbitMQ consumer for rescrape jobs.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Callable, Optional

import pika
from pika.adapters.blocking_connection import BlockingChannel
from pika.spec import Basic, BasicProperties

from application.domain.services.rescrape_job_service import RescrapeJobService
from configuration.rabbitmq_configuration import get_rabbitmq_connection
from configuration.settings_configuration import settings

logger = logging.getLogger(__name__)


class RescrapeJobConsumer:
    def __init__(self, service_factory: Callable[[], tuple[RescrapeJobService, Callable[[], None]]]):
        self._service_factory = service_factory
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[BlockingChannel] = None
        self.should_stop = False

    def _connect(self) -> None:
        max_retries = 5
        retry_delay_seconds = 5

        for attempt in range(max_retries):
            try:
                self.connection = get_rabbitmq_connection()
                self.channel = self.connection.channel()
                self.channel.basic_qos(prefetch_count=1)
                self.channel.queue_declare(queue=settings.rescrape_rabbit_queue, durable=True)
                logger.info("RescrapeJobConsumer conectado no RabbitMQ (queue=%s)", settings.rescrape_rabbit_queue)
                return
            except Exception as exc:
                logger.error(
                    "Falha ao conectar consumidor de rescrape no RabbitMQ (tentativa %s/%s): %s",
                    attempt + 1,
                    max_retries,
                    exc,
                )
                if attempt < max_retries - 1:
                    time.sleep(retry_delay_seconds)
                else:
                    raise

    def _process_message(
        self,
        channel: BlockingChannel,
        method: Basic.Deliver,
        properties: BasicProperties,
        body: bytes,
    ) -> None:
        delivery_tag = method.delivery_tag
        try:
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            logger.error("Mensagem inválida na fila de rescrape: %s", exc)
            self._safe_nack(channel, delivery_tag=delivery_tag, requeue=False)
            return

        job_id = payload.get("job_id") if isinstance(payload, dict) else None
        if not isinstance(job_id, int) or job_id <= 0:
            logger.error("Mensagem de rescrape sem job_id válido: %s", payload)
            self._safe_nack(channel, delivery_tag=delivery_tag, requeue=False)
            return

        try:
            service, cleanup = self._service_factory()
            try:
                processed = service.process_job_by_id(job_id)
                if not processed:
                    logger.warning("Job de rescrape %s não encontrado ou não elegível", job_id)
                self._safe_ack(channel, delivery_tag=delivery_tag)
            finally:
                cleanup()
        except Exception as exc:
            logger.error("Erro ao processar job de rescrape %s: %s", job_id, exc, exc_info=True)
            self._safe_nack(channel, delivery_tag=delivery_tag, requeue=False)

    @staticmethod
    def _safe_ack(channel: BlockingChannel, *, delivery_tag: int) -> None:
        try:
            if channel.is_open:
                channel.basic_ack(delivery_tag=delivery_tag)
        except Exception as exc:
            logger.error("Falha no ACK do rescrape %s: %s", delivery_tag, exc)

    @staticmethod
    def _safe_nack(channel: BlockingChannel, *, delivery_tag: int, requeue: bool) -> None:
        try:
            if channel.is_open:
                channel.basic_nack(delivery_tag=delivery_tag, requeue=requeue)
        except Exception as exc:
            logger.error("Falha no NACK do rescrape %s: %s", delivery_tag, exc)

    def start(self) -> None:
        logger.info("Iniciando consumo RabbitMQ na fila %s", settings.rescrape_rabbit_queue)

        while not self.should_stop:
            try:
                self._connect()
                if self.channel is None:
                    raise RuntimeError("Channel RabbitMQ não inicializado")

                self.channel.basic_consume(
                    queue=settings.rescrape_rabbit_queue,
                    on_message_callback=self._process_message,
                    auto_ack=False,
                )
                self.channel.start_consuming()
            except Exception as exc:
                if self.should_stop:
                    break
                logger.error("Falha no loop do consumidor de rescrape: %s", exc, exc_info=True)
                self._cleanup()
                time.sleep(5)
            finally:
                self._cleanup()

    def stop(self) -> None:
        self.should_stop = True
        if self.connection and self.connection.is_open and self.channel and self.channel.is_open:
            try:
                self.connection.add_callback_threadsafe(self.channel.stop_consuming)
            except Exception:
                pass
        self._cleanup()

    def _cleanup(self) -> None:
        if self.channel and self.channel.is_open:
            self.channel.close()
        if self.connection and not self.connection.is_closed:
            self.connection.close()
        self.channel = None
        self.connection = None
