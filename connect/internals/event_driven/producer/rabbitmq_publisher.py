import json
from time import sleep

from django.conf import settings

from pika import BasicProperties
from pika.exceptions import StreamLostError

from typing import Dict

from connect.internals.event_driven.connection.rabbitmq import RabbitMQConnection


class RabbitmqPublisher:  # pragma: no cover
    def __init__(self) -> None:
        self.rabbitmq_connection = RabbitMQConnection()

    def send_message(self, body: Dict, exchange: str, routing_key: str):
        sended = False
        while not sended:
            try:
                self.rabbitmq_connection.channel.basic_publish(
                    exchange=exchange,
                    routing_key=routing_key,
                    body=json.dumps(body),
                    properties=BasicProperties(delivery_mode=2),
                )
                print(f"Message sent {body}")
                sended = True
            except StreamLostError as e:
                print(f"stream lost error: {e}")
                self.rabbitmq_connection.make_connection()
            except Exception as err:
                print(f"error: {err}")
                self.rabbitmq_connection.make_connection()
            if not sended:
                sleep(settings.EDA_WAIT_TIME_RETRY)
