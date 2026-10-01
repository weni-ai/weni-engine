from weni.eda.channels import Channel

from connect.change_history.handle import (
    handle_consumers as change_history_handle_consumers,
)
from connect.recent_activities.handle import (
    handle_consumers as recent_activities_handle_consumers,
)


def handle_edaconsume(channel: Channel) -> None:
    """RabbitMQ consumers (EDA_* / no SSL)."""
    recent_activities_handle_consumers(channel)


def handle_edaconsume_amq(channel: Channel) -> None:
    """AmazonMQ consumers (AMQ_* / SSL)."""
    change_history_handle_consumers(channel)
