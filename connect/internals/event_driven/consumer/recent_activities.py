import amqp

from sentry_sdk import capture_exception
from .rabbitmq_consumer import EDAConsumer

from connect.usecases.recent_activities.create import RecentActivityUseCase

from .parsers.json_parser import JSONParser
from connect.usecases.recent_activities.exceptions import InvalidActionEntityCombination


class RecentActivitiesConsumer(EDAConsumer):
    def consume(self, message: amqp.Message):
        try:
            msg_body = JSONParser.parse(message.body)
            print(f"[RecentActivitiesConsumer] - Consuming a message. Body: {msg_body}")
            usecase = RecentActivityUseCase()
            usecase.create_recent_activity(msg_body)

            message.channel.basic_ack(message.delivery_tag)
            print("[RecentActivitiesConsumer] - Recent activity created.")
        except InvalidActionEntityCombination as exception:
            capture_exception(exception)
            message.channel.basic_reject(message.delivery_tag, requeue=False)
            print(
                f"[RecentActivitiesConsumer] - Message rejected due to invalid action/entity combination: {exception}"
            )
        except Exception as exception:
            capture_exception(exception)
            message.channel.basic_reject(message.delivery_tag, requeue=False)
            print(f"[RecentActivitiesConsumer] - Message rejected by: {exception}")
