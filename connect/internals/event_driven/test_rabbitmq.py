from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from pika.exceptions import AMQPConnectionError, StreamLostError

from connect.internals.event_driven.connection.rabbitmq import (
    BLOCKED_CONNECTION_TIMEOUT,
    CONNECT_RETRY_DELAY,
    RabbitMQConnection,
    SOCKET_TIMEOUT,
)
from connect.internals.event_driven.producer.rabbitmq_publisher import (
    MAX_PUBLISH_RETRIES,
    RabbitmqPublisher,
)


class RabbitMQConnectionTestCase(TestCase):
    def setUp(self):
        RabbitMQConnection._instance = None

    def tearDown(self):
        RabbitMQConnection._instance = None

    def _override_broker_settings(self):
        return override_settings(
            EDA_BROKER_HOST="localhost",
            EDA_BROKER_PORT=5672,
            EDA_BROKER_USER="guest",
            EDA_BROKER_PASSWORD="guest",
            EDA_VIRTUAL_HOST="/",
        )

    @patch("connect.internals.event_driven.connection.rabbitmq.BlockingConnection")
    def test_make_connection_closes_stale_socket_and_reestablishes(
        self, mock_blocking
    ):
        stale_connection = Mock()
        stale_connection.is_open = True
        stale_channel = Mock()
        stale_channel.is_open = True
        stale_connection.channel.return_value = stale_channel

        fresh_connection = Mock()
        fresh_connection.is_open = True
        fresh_channel = Mock()
        fresh_channel.is_open = True
        fresh_connection.channel.return_value = fresh_channel

        mock_blocking.side_effect = [stale_connection, fresh_connection]

        with self._override_broker_settings():
            connection = RabbitMQConnection()
            reopened = connection.make_connection()

        self.assertTrue(reopened)
        stale_connection.close.assert_called_once()
        self.assertEqual(connection.connection, fresh_connection)
        self.assertEqual(connection.channel, fresh_channel)
        self.assertEqual(mock_blocking.call_count, 2)

    @patch("connect.internals.event_driven.connection.rabbitmq.BlockingConnection")
    def test_ensure_connected_skips_when_already_ready(self, mock_blocking):
        live_connection = Mock()
        live_connection.is_open = True
        live_channel = Mock()
        live_channel.is_open = True
        live_connection.channel.return_value = live_channel
        mock_blocking.return_value = live_connection

        with self._override_broker_settings():
            connection = RabbitMQConnection()
            connection.ensure_connected()

        self.assertEqual(mock_blocking.call_count, 1)

    @patch("connect.internals.event_driven.connection.rabbitmq.BlockingConnection")
    def test_ensure_connected_reconnects_when_channel_is_closed(self, mock_blocking):
        stale_connection = Mock()
        stale_connection.is_open = True
        stale_channel = Mock()
        stale_channel.is_open = False
        stale_connection.channel.return_value = stale_channel

        fresh_connection = Mock()
        fresh_connection.is_open = True
        fresh_channel = Mock()
        fresh_channel.is_open = True
        fresh_connection.channel.return_value = fresh_channel
        mock_blocking.side_effect = [stale_connection, fresh_connection]

        with self._override_broker_settings():
            connection = RabbitMQConnection()
            connection.ensure_connected()

        self.assertEqual(connection.channel, fresh_channel)

    @patch("connect.internals.event_driven.connection.rabbitmq.BlockingConnection")
    def test_publish_message_uses_open_channel(self, mock_blocking):
        live_connection = Mock()
        live_connection.is_open = True
        live_channel = Mock()
        live_channel.is_open = True
        live_connection.channel.return_value = live_channel
        mock_blocking.return_value = live_connection
        properties = Mock()

        with self._override_broker_settings():
            connection = RabbitMQConnection()
            connection.publish_message(
                exchange="projects.topic",
                routing_key="",
                body=b'{"uuid": "1"}',
                properties=properties,
            )

        live_channel.basic_publish.assert_called_once_with(
            exchange="projects.topic",
            routing_key="",
            body=b'{"uuid": "1"}',
            properties=properties,
        )

    @patch("connect.internals.event_driven.connection.rabbitmq.BlockingConnection")
    def test_connection_parameters_disable_heartbeat(self, mock_blocking):
        live_connection = Mock()
        live_connection.is_open = True
        live_channel = Mock()
        live_channel.is_open = True
        live_connection.channel.return_value = live_channel
        mock_blocking.return_value = live_connection

        with self._override_broker_settings():
            RabbitMQConnection()

        params = mock_blocking.call_args.args[0]
        self.assertEqual(params.heartbeat, 0)
        self.assertEqual(params.blocked_connection_timeout, BLOCKED_CONNECTION_TIMEOUT)
        self.assertEqual(params.socket_timeout, SOCKET_TIMEOUT)

    @patch("connect.internals.event_driven.connection.rabbitmq.time.sleep")
    @patch("connect.internals.event_driven.connection.rabbitmq.BlockingConnection")
    def test_connect_retries_once_on_amqp_connection_error(
        self, mock_blocking, mock_sleep
    ):
        live_connection = Mock()
        live_connection.is_open = True
        live_channel = Mock()
        live_channel.is_open = True
        live_connection.channel.return_value = live_channel
        mock_blocking.side_effect = [
            AMQPConnectionError("broker down"),
            live_connection,
        ]

        with self._override_broker_settings():
            connection = RabbitMQConnection()

        mock_sleep.assert_called_once_with(CONNECT_RETRY_DELAY)
        self.assertEqual(connection.connection, live_connection)
        self.assertEqual(mock_blocking.call_count, 2)

    @patch("connect.internals.event_driven.connection.rabbitmq.time.sleep")
    @patch("connect.internals.event_driven.connection.rabbitmq.BlockingConnection")
    def test_connect_reraises_when_retry_also_fails(self, mock_blocking, mock_sleep):
        mock_blocking.side_effect = AMQPConnectionError("broker down")

        with self._override_broker_settings():
            with self.assertRaises(AMQPConnectionError):
                RabbitMQConnection()

        mock_sleep.assert_called_once_with(CONNECT_RETRY_DELAY)
        self.assertEqual(mock_blocking.call_count, 2)

    @patch("connect.internals.event_driven.connection.rabbitmq.BlockingConnection")
    def test_connect_reraises_unexpected_errors(self, mock_blocking):
        mock_blocking.side_effect = ValueError("bad config")

        with self._override_broker_settings():
            with self.assertRaises(ValueError):
                RabbitMQConnection()

        self.assertEqual(mock_blocking.call_count, 1)

    @patch("connect.internals.event_driven.connection.rabbitmq.BlockingConnection")
    def test_close_closes_open_connection(self, mock_blocking):
        live_connection = Mock()
        live_connection.is_open = True
        live_channel = Mock()
        live_channel.is_open = True
        live_connection.channel.return_value = live_channel
        mock_blocking.return_value = live_connection

        with self._override_broker_settings():
            connection = RabbitMQConnection()
            connection.close()

        live_connection.close.assert_called_once()


class RabbitmqPublisherTestCase(TestCase):
    @override_settings(TESTING=False, EDA_WAIT_TIME_RETRY=0)
    @patch("connect.internals.event_driven.producer.rabbitmq_publisher.sleep")
    @patch(
        "connect.internals.event_driven.producer.rabbitmq_publisher.RabbitMQConnection"
    )
    def test_send_message_reconnects_after_broken_pipe_and_succeeds(
        self, mock_connection_cls, mock_sleep
    ):
        mock_connection = Mock()
        mock_connection_cls.return_value = mock_connection
        mock_connection.publish_message.side_effect = [
            BrokenPipeError(32, "Broken pipe"),
            None,
        ]

        publisher = RabbitmqPublisher()
        publisher.send_message(
            body={"uuid": "1"}, exchange="projects.topic", routing_key=""
        )

        self.assertEqual(mock_connection.publish_message.call_count, 2)
        mock_connection.make_connection.assert_called_once()
        mock_sleep.assert_called_once_with(0)

    @override_settings(TESTING=False, EDA_WAIT_TIME_RETRY=0)
    @patch("connect.internals.event_driven.producer.rabbitmq_publisher.sleep")
    @patch(
        "connect.internals.event_driven.producer.rabbitmq_publisher.RabbitMQConnection"
    )
    def test_send_message_raises_after_retries_exhausted(
        self, mock_connection_cls, mock_sleep
    ):
        mock_connection = Mock()
        mock_connection_cls.return_value = mock_connection
        mock_connection.publish_message.side_effect = StreamLostError("stream lost")

        publisher = RabbitmqPublisher()

        with self.assertRaises(StreamLostError):
            publisher.send_message(
                body={"uuid": "1"}, exchange="orgs.topic", routing_key=""
            )

        self.assertEqual(
            mock_connection.publish_message.call_count, MAX_PUBLISH_RETRIES
        )
        self.assertEqual(mock_connection.make_connection.call_count, MAX_PUBLISH_RETRIES)

    @override_settings(TESTING=True)
    @patch(
        "connect.internals.event_driven.producer.rabbitmq_publisher.RabbitMQConnection"
    )
    def test_send_message_is_noop_during_tests(self, mock_connection_cls):
        publisher = RabbitmqPublisher()
        publisher.send_message(
            body={"uuid": "1"}, exchange="projects.topic", routing_key=""
        )

        mock_connection_cls.assert_not_called()
