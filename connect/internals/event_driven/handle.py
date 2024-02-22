from amqp.channel import Channel

from .consumer.recent_activities import RecentActivitiesConsumer


def handle_consumers(
        channel: Channel
) -> None:

    channel.basic_consume(
        "recent-activity.projects",
        callback=RecentActivitiesConsumer().handle
    )
