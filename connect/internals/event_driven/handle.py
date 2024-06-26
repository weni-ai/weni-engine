from amqp.channel import Channel

from .consumer.recent_activities import RecentActivitiesConsumer


# Event driven using rabbitmq handles consumers
def handle_consumers(channel: Channel) -> None:

    channel.basic_consume(
        "recent-activity.connect", callback=RecentActivitiesConsumer().handle
    )
