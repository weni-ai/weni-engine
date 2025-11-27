import time
import amqp

from django.conf import settings


class RabbitMQPymqpConnection:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RabbitMQPymqpConnection, cls).__new__(cls)
            cls._instance.connect()
        return cls._instance

    def _establish_connection(self):
        connection_params = {
            "host": settings.EDA_BROKER_HOST,
            "virtual_host": settings.EDA_VIRTUAL_HOST,
            "userid": settings.EDA_BROKER_USER,
            "password": settings.EDA_BROKER_PASSWORD,
            "port": settings.EDA_BROKER_PORT,
        }

        if settings.EDA_BROKER_USE_SSL:
            # PyAMQP supports SSL via the 'ssl' parameter
            # For AWS MQ, we use ssl=True without certificate verification
            # as AWS MQ uses self-signed certificates
            connection_params["ssl"] = True

        self.connection = amqp.Connection(**connection_params)
        self.channel = self.connection.channel()

    def connect(self):
        try:
            if not hasattr(self, "connection"):
                self._establish_connection()
        except Exception as e:
            print("Error while connecting to RabbitMQ:", str(e))
            time.sleep(5)  # Wait until try to reconnect
            self._establish_connection()

    def make_connection(self):
        if self.connection.is_closing:
            self._establish_connection()
        return self.connection.is_alive


class PyAMQPConnectionBackend:
    _start_message = "[+] Connection established. Waiting for events"

    def __init__(self, handle_consumers: callable):
        self._handle_consumers = handle_consumers
        self.rabbitmq_instance = RabbitMQPymqpConnection()

    def _drain_events(self, connection: amqp.connection.Connection):
        while True:
            connection.drain_events()

    def start_consuming(self):
        while True:
            try:
                channel = self.rabbitmq_instance.channel

                self._handle_consumers(channel)

                print(self._start_message)

                self._drain_events(self.rabbitmq_instance.connection)

            except (
                amqp.exceptions.AMQPError,
                ConnectionRefusedError,
                OSError,
            ) as error:
                print(f"[-] Connection error: {error}")
                print("    [+] Reconnecting in 5 seconds...")
                time.sleep(5)
                self.rabbitmq_instance._establish_connection()
            except Exception as error:
                # TODO: Handle exceptions with RabbitMQ
                print("error on drain_events:", type(error), error)
                time.sleep(5)
                self.rabbitmq_instance._establish_connection()
