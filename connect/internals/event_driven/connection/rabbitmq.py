import time

from pika import BlockingConnection, ConnectionParameters, PlainCredentials

from django.conf import settings


class RabbitMQConnection:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RabbitMQConnection, cls).__new__(cls)
            cls._instance.connect()
        return cls._instance

    def make_connection(self):
        if self.connection.is_closed:
            self._establish_connection()
        return self.connection.is_open

    def connect(self):
        try:
            if not hasattr(self, "connection"):
                self._establish_connection()
        except Exception as e:
            print("Error while connecting to RabbitMQ:", str(e))
            time.sleep(5)  # Espera antes de tentar reconectar
            self._establish_connection()

    def _establish_connection(self):
        self.connection = BlockingConnection(ConnectionParameters(
            host=settings.EDA_BROKER_HOST,
            port=settings.EDA_BROKER_PORT,
            credentials=PlainCredentials(
                username=settings.EDA_BROKER_USER,
                password=settings.EDA_BROKER_PASSWORD
            ),
            virtual_host=settings.EDA_VIRTUAL_HOST
        ))
        self.channel = self.connection.channel()

    def close(self):
        if hasattr(self, "connection"):
            self.connection.close()