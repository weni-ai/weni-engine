from django.conf import settings

from connect.celery import app as celery_app
from connect.common.models import Project
from connect.internals.event_driven.producer.rabbitmq_publisher import RabbitmqPublisher


class UpdateProjectUseCase:
    def send_updated_project(self, project: Project, user_email: str):
        message_body = {
            "project_uuid": str(project.uuid),
            "description": project.description,
            "user_email": user_email,
        }

        celery_app.send_task(
            "update_project",
            args=[project.uuid, project.name],
        )

        if not settings.TESTING:
            self.rabbitmq_publisher = RabbitmqPublisher()
            self.rabbitmq_publisher.send_message(
                message_body, exchange="update-projects.topic", routing_key=""
            )
