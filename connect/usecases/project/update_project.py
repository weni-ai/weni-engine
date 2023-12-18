from django.conf import settings

from connect.api.v1.internal.chats.chats_rest_client import ChatsRESTClient
from connect.celery import app as celery_app
from connect.common.models import Project
from connect.internals.event_driven.producer.rabbitmq_publisher import RabbitmqPublisher

class UpdateProjectUseCase:

    def __init__(self):
        self.rabbitmq_publisher = RabbitmqPublisher()

    def send_updated_project(self, project: Project, user_email: str):
        message_body = {
            "project_uuid": str(project.uuid),
            "description": project.description,
            "user_email": user_email
        }

        celery_app.send_task(
            "update_project",
            args=[project.uuid, project.name],
        )

        self.rabbitmq_publisher.send_message(message_body, exchange="update-projects.topic", routing_key="")
