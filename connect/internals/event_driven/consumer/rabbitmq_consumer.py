from abc import ABC, abstractmethod

from connect.internals.event_driven.signals import message_started, message_finished


class EDAConsumer(ABC):
    def handle(self, message):
        """
        Handle a message (works with both amqp.Message and PikaMessageAdapter)
        """
        message_started.send(sender=self)
        try:
            self.consume(message)
        finally:
            message_finished.send(sender=self)

    @abstractmethod
    def consume(self, message):
        """
        Consume a message. The message object will have:
        - message.body: bytes
        - message.delivery_tag: int
        - message.channel: channel adapter with basic_ack and basic_reject methods
        """
        pass
