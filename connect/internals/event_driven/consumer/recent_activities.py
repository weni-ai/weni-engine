import amqp

from sentry_sdk import capture_exception
from .rabbitmq_consumer import EDAConsumer

from connect.usecases.recent_activities.create import RecentActivityUseCase

from .parsers.json_parser import JSONParser


class RecentActivitiesConsumer(EDAConsumer):

    def consume(self, message: amqp.Message):
        try:
            body = JSONParser.parse(message.body)
            print(f"[RecentActivitiesConsumer] - Consuming a message. Body: {body}")
            usecase = RecentActivityUseCase()
            usecase.create_recent_activity(
                user_email=body.get("user"),
                project_uuid=body.get("project_uuid"),
                action=body.get("action"),
                entity=body.get("entity"),
                entity_name=body.get("entity_name")
            )

            message.channel.basic_ack(message.delivery_tag)
            print("[RecentActivitiesConsumer] - Recent activity created.")
        except Exception as exception:
            capture_exception(exception)
            message.channel.basic_reject(message.delivery_tag, requeue=False)
            print(f"[RecentActivitiesConsumer] - Message rejected by: {exception}")
