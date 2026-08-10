from weni.eda.channels import Channel

from .consumers.recent_activity import RecentActivitiesConsumer


def handle_consumers(channel: Channel) -> None:
    channel.basic_consume(
        "recent-activity.connect", callback=RecentActivitiesConsumer().handle
    )
