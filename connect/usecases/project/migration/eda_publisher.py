from typing import Optional, Union
from uuid import UUID

import pendulum
from django.conf import settings
from weni.eda.django.connection_params import AMQConnectionParamsFactory
from weni.eda.eda_publisher import EDAPublisher


class ProjectMigrationEDAPublisher:
    """
    Publisher for project migration events via AmazonMQ (weni-eda).

    Publishes to exchange 'projects.topic' with routing key 'project.migrated'.
    """

    EXCHANGE = "projects.topic"
    ROUTING_KEY = "project.migrated"
    EVENT_TYPE = "engine.project.migrated"
    PRODUCER = "weni-engine"

    def __init__(self):
        if settings.USE_PROJECT_MIGRATION_PUBLISHER and not settings.TESTING:
            self.eda_publisher = EDAPublisher(AMQConnectionParamsFactory)
        else:
            self.eda_publisher = None

    def publish_project_migrated(
        self,
        event_id: Union[UUID, str],
        project_uuid: Union[UUID, str],
        org_from: Union[UUID, str],
        org_to: Union[UUID, str],
        timestamp: Optional[pendulum.DateTime] = None,
    ) -> None:
        """Publish a project migrated event to AmazonMQ."""
        if not self.eda_publisher:
            return

        if timestamp is None:
            timestamp = pendulum.now("UTC")

        message_body = {
            "event_id": str(event_id),
            "event_type": self.EVENT_TYPE,
            "producer": self.PRODUCER,
            "timestamp": timestamp.to_iso8601_string(),
            "data": {
                "uuid": str(project_uuid),
                "org": {
                    "from": str(org_from),
                    "to": str(org_to),
                },
            },
        }

        self.eda_publisher.send_message(
            message_body,
            exchange=self.EXCHANGE,
            routing_key=self.ROUTING_KEY,
        )
