"""
RabbitMQ Configuration
"""
import pika

from configuration.settings_configuration import settings


def get_rabbitmq_connection() -> pika.BlockingConnection:
    credentials = pika.PlainCredentials(settings.rabbitmq_user, settings.rabbitmq_password)
    parameters = pika.ConnectionParameters(
        host=settings.rabbitmq_host,
        port=settings.rabbitmq_port,
        credentials=credentials,
    )
    return pika.BlockingConnection(parameters)


def get_rabbitmq_channel() -> pika.channel.Channel:
    connection = get_rabbitmq_connection()
    return connection.channel()
