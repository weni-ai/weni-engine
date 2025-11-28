"""
Adapter to make pika API compatible with amqp API for consumers
"""
from typing import Any

import pika


class PikaMessageAdapter:
    """
    Adapter that wraps pika's callback parameters into an amqp.Message-like object
    """

    def __init__(self, channel: pika.channel.Channel, method: Any, properties: Any, body: bytes):
        self._channel = channel
        self._method = method
        self._properties = properties
        self.body = body
        self.delivery_tag = method.delivery_tag

    @property
    def channel(self):
        """Return the channel with amqp-like interface"""
        return PikaChannelAdapter(self._channel)


class PikaChannelAdapter:
    """
    Adapter that wraps pika's channel to provide amqp-like interface
    """

    def __init__(self, channel: pika.channel.Channel):
        self._channel = channel

    def basic_ack(self, delivery_tag: int):
        """Acknowledge a message"""
        self._channel.basic_ack(delivery_tag=delivery_tag)

    def basic_reject(self, delivery_tag: int, requeue: bool = False):
        """Reject a message"""
        self._channel.basic_reject(delivery_tag=delivery_tag, requeue=requeue)


def create_pika_callback(consumer_instance):
    """
    Creates a pika-compatible callback from an amqp consumer
    """
    def callback(ch: pika.channel.Channel, method: Any, properties: Any, body: bytes):
        # Create adapter to make it compatible with amqp.Message interface
        message = PikaMessageAdapter(ch, method, properties, body)
        consumer_instance.handle(message)

    return callback

