import json
import logging
from time import sleep

from django.conf import settings

from pika import BasicProperties
from pika.exceptions import AMQPError

from connect.internals.event_driven.connection.rabbitmq import RabbitMQConnection

logger = logging.getLogger(__name__)

MAX_PUBLISH_RETRIES = 3


class RabbitmqPublisher:
    def __init__(self) -> None:
        # Tests must never reach a real broker (project convention: EDA
        # publishers are no-ops under settings.TESTING). Skip the connection so
        # signal/model side effects don't hit external infrastructure.
        self.rabbitmq_connection = None if settings.TESTING else RabbitMQConnection()

    def send_message(self, body: dict, exchange: str, routing_key: str):
        if settings.TESTING:
            return

        last_error = None
        for attempt in range(1, MAX_PUBLISH_RETRIES + 1):
            try:
                self._publish(body, exchange, routing_key)
                logger.info(f"Published message to exchange={exchange}")
                return
            except (AMQPError, OSError) as exc:
                last_error = exc
                logger.exception(
                    f"Failed to publish to exchange={exchange} "
                    f"(attempt {attempt}/{MAX_PUBLISH_RETRIES})"
                )
                self.rabbitmq_connection.make_connection()
                if attempt < MAX_PUBLISH_RETRIES:
                    sleep(settings.EDA_WAIT_TIME_RETRY)

        raise last_error

    def _publish(self, body: dict, exchange: str, routing_key: str):
        self.rabbitmq_connection.publish_message(
            exchange=exchange,
            routing_key=routing_key,
            body=json.dumps(body),
            properties=BasicProperties(delivery_mode=2),
        )
