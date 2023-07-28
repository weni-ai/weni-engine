from pika import BlockingConnection, ConnectionParameters, PlainCredentials
from django.conf import settings


class RabbitMQConnection:  # pragma: no cover
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RabbitMQConnection, cls).__new__(cls)
            cls._instance.connect()
        return cls._instance

    def connect(self):
        if not hasattr(self, "connection"):
            self.connection = BlockingConnection(ConnectionParameters(
                host=settings.EDA_BROKER_HOST,
                port=settings.EDA_BROKER_PORT,
                virtual_host=settings.EDA_VIRTUAL_HOST,
                credentials=PlainCredentials(
                    username=settings.EDA_BROKER_USER,
                    password=settings.EDA_BROKER_PASSWORD
                )
            ))
            self.channel = self.connection.channel()

    def close(self):
        if hasattr(self, "connection"):
            self.connection.close()
