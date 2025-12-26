from typing import Optional
from uuid import UUID

import pendulum
from django.conf import settings

from connect.internals.event_driven.producer.rabbitmq_publisher import RabbitmqPublisher


class ProjectEDAPublisher:
    """
    Publisher for project-related events via EDA (Event-Driven Architecture).

    Publishes to exchange 'update-projects.topic' with routing keys:
    - project.deleted
    - project.updated
    """

    def __init__(self):
        if settings.USE_EDA and not settings.TESTING:
            self.rabbitmq_publisher = RabbitmqPublisher()
        else:
            self.rabbitmq_publisher = None

    def publish_project_deleted(
        self,
        project_uuid: UUID,
        user_email: str,
        deleted_at: Optional[pendulum.DateTime] = None,
    ) -> None:
        """
        Publish a project deleted event.

        Args:
            project_uuid: UUID of the deleted project
            user_email: Email of the user who deleted the project
            deleted_at: Timestamp of deletion (defaults to now)
        """
        if not self.rabbitmq_publisher:
            return

        if deleted_at is None:
            deleted_at = pendulum.now("UTC")

        message_body = {
            "project_uuid": str(project_uuid),
            "action": "deleted",
            "user_email": user_email,
            "timestamp": deleted_at.to_iso8601_string(),
        }

        self.rabbitmq_publisher.send_message(
            body=message_body,
            exchange="update-projects.topic",
            routing_key="project.deleted",
        )

    def publish_project_updated(
        self,
        project_uuid: UUID,
        user_email: str,
        description: Optional[str] = None,
        language: Optional[str] = None,
        updated_at: Optional[pendulum.DateTime] = None,
    ) -> None:
        """
        Publish a project updated event.

        Args:
            project_uuid: UUID of the updated project
            user_email: Email of the user who updated the project
            description: New project description
            language: New project language
            updated_at: Timestamp of update (defaults to now)
        """
        if not self.rabbitmq_publisher:
            return

        if updated_at is None:
            updated_at = pendulum.now("UTC")

        message_body = {
            "project_uuid": str(project_uuid),
            "action": "updated",
            "user_email": user_email,
            "description": description,
            "language": language,
            "timestamp": updated_at.to_iso8601_string(),
        }

        self.rabbitmq_publisher.send_message(
            body=message_body,
            exchange="update-projects.topic",
            routing_key="project.updated",
        )

