import logging

from weni.eda.django.consumers import EDAConsumer
from weni.eda.messages import Message

from connect.usecases.recent_activities.create import RecentActivityUseCase


logger = logging.getLogger(__name__)


class RecentActivitiesConsumer(EDAConsumer):
    def consume(self, message: Message):
        body = message.json()
        logger.info("Consuming recent activity message")
        RecentActivityUseCase().create_recent_activity(body)
        self.ack()
        logger.info("Recent activity created")
