import amqp

from sentry_sdk import capture_exception
from .rabbitmq_consumer import EDAConsumer

from connect.usecases.recent_activities.create import RecentActivityUseCase


class RecentActivitiesConsumer(EDAConsumer):

    def consume(self, message: amqp.Message):
        print(f"[RecentActivitiesConsumer] - Consuming a message. Body: {message.body}")
        try:
            usecase = RecentActivityUseCase()
            usecase.create_recent_activity(
                user_email=message.body["user_email"],
                project_uuid=message.body["project_uuid"],
                action=message.body["action"],
                entity=message.body["entity"],
                entity_name=message.body["entity_name"]
            )

            message.channel.basic_ack(message.delivery_tag)
            print("[RecentActivitiesConsumer] - Recent activity created.")
        except Exception as exception:
            capture_exception(exception)
            message.channel.basic_reject(message.delivery_tag, requeue=False)
            print(f"[RecentActivitiesConsumer] - Message rejected by: {exception}")
