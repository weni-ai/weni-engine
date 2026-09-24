from weni.eda.channels import Channel

from .consumers.change_event import ChangeEventConsumer


def handle_consumers(channel: Channel) -> None:
    channel.basic_consume(
        "connect.change-event.queue", callback=ChangeEventConsumer().handle
    )
