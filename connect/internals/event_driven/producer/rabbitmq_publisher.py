import json

from pika import BasicProperties
from typing import Dict

from connect.internals.event_driven.connection.rabbitmq import RabbitMQConnection


class RabbitmqPublisher:  # pragma: no cover
    def __init__(self) -> None:
        self.rabbitmq_connection = RabbitMQConnection()

    def send_message(self, body: Dict, exchange: str, routing_key: str):
        try:
            self.rabbitmq_connection.channel.basic_publish(
                exchange=exchange,
                routing_key=routing_key,
                body=json.dumps(body),
                properties=BasicProperties(
                    delivery_mode=2
                )
            )
            print("Message sent")
        except Exception as e:
            print(e)
            raise e
