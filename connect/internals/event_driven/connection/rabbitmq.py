import logging
import threading
import time

from pika import BlockingConnection, ConnectionParameters, PlainCredentials
from pika.exceptions import AMQPConnectionError

from django.conf import settings

logger = logging.getLogger(__name__)

BLOCKED_CONNECTION_TIMEOUT = 10
SOCKET_TIMEOUT = 10
CONNECT_RETRY_DELAY = 5


class RabbitMQConnection:
    _instance = None
    _lock = threading.RLock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance.connect()
        return cls._instance

    def make_connection(self):
        """Close any existing socket and open a new one.

        Must be used after a publish failure: pika can still report
        ``is_open=True`` on a half-dead connection (BrokenPipe / missed
        heartbeat), so checking ``is_closed`` is not enough.
        """
        with self._lock:
            self._close_quietly()
            self._establish_connection()
            return self.connection.is_open

    def ensure_connected(self):
        with self._lock:
            if not self._is_ready():
                self.make_connection()

    def connect(self):
        try:
            if not self._is_ready():
                self._establish_connection()
        except AMQPConnectionError:
            logger.exception("Error while connecting to RabbitMQ")
            time.sleep(CONNECT_RETRY_DELAY)
            self._establish_connection()

    def publish_message(self, exchange: str, routing_key: str, body: bytes, properties):
        with self._lock:
            self.ensure_connected()
            self.channel.basic_publish(
                exchange=exchange,
                routing_key=routing_key,
                body=body,
                properties=properties,
            )

    def close(self):
        with self._lock:
            self._close_quietly()

    def _is_ready(self) -> bool:
        connection = getattr(self, "connection", None)
        channel = getattr(self, "channel", None)
        return bool(
            connection is not None
            and connection.is_open
            and channel is not None
            and channel.is_open
        )

    def _close_quietly(self):
        connection = getattr(self, "connection", None)
        if connection is None:
            return
        try:
            if connection.is_open:
                connection.close()
        except Exception as exc:
            logger.warning(f"Error while closing stale RabbitMQ connection: {exc}")

    def _establish_connection(self):
        # heartbeat=0: gunicorn/gevent workers do not call process_data_events
        # between requests, so a negotiated heartbeat would make RabbitMQ close
        # the idle singleton socket (BrokenPipe on the next publish).
        self.connection = BlockingConnection(
            ConnectionParameters(
                host=settings.EDA_BROKER_HOST,
                port=settings.EDA_BROKER_PORT,
                credentials=PlainCredentials(
                    username=settings.EDA_BROKER_USER,
                    password=settings.EDA_BROKER_PASSWORD,
                ),
                virtual_host=settings.EDA_VIRTUAL_HOST,
                heartbeat=0,
                blocked_connection_timeout=BLOCKED_CONNECTION_TIMEOUT,
                socket_timeout=SOCKET_TIMEOUT,
            )
        )
        self.channel = self.connection.channel()
