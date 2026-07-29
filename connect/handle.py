from amqp.channel import Channel

from connect.change_history.handle import handle_consumers as change_history_handle_consumers


def handle_consumers(channel: Channel) -> None:
    change_history_handle_consumers(channel)
