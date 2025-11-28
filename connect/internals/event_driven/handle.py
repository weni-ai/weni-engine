from .consumer.recent_activities import RecentActivitiesConsumer
from .consumer.pika_adapter import create_pika_callback


# Event driven using rabbitmq handles consumers
# Supports both pika and amqp channels
def handle_consumers(channel) -> None:
    """
    Register consumers for the given channel.
    Works with both pika (RabbitMQConnection) and amqp (RabbitMQPymqpConnection) channels.
    """
    # Try to detect if it's pika or amqp by checking the channel type
    channel_module = type(channel).__module__
    
    if 'pika' in channel_module:
        # It's a pika channel
        consumer = RecentActivitiesConsumer()
        callback = create_pika_callback(consumer)
        channel.basic_consume(
            queue="recent-activity.connect",
            on_message_callback=callback,
            auto_ack=False
        )
    else:
        # It's an amqp channel (original implementation)
        channel.basic_consume(
            "recent-activity.connect", callback=RecentActivitiesConsumer().handle
        )
