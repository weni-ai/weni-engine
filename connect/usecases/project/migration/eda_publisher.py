from typing import Union
from uuid import UUID

from django.conf import settings
from weni.eda.django.connection_params import AMQConnectionParamsFactory
from weni.eda.eda_publisher import EDAPublisher
from weni.eda.events import Event


class ProjectMigrationEDAPublisher:
    """
    Publisher for project migration events via AmazonMQ (weni-eda).

    Publishes to exchange 'projects.topic' with routing key 'project.migrated'.
    """

    EXCHANGE = "projects.topic"
    ROUTING_KEY = "project.migrated"
    EVENT_TYPE = "project.migrated"

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
    ) -> None:
        """Publish a project migrated event to AmazonMQ."""
        if not self.eda_publisher:
            return

        event = Event.build(
            self.EVENT_TYPE,
            {
                "uuid": str(project_uuid),
                "org": {
                    "from": str(org_from),
                    "to": str(org_to),
                },
            },
            producer=settings.EDA_PRODUCER,
        )
        # Keep correlation with ProjectMigration.uuid for status callbacks.
        event.event_id = str(event_id)

        self.eda_publisher.send_message(
            event.to_dict(),
            exchange=self.EXCHANGE,
            routing_key=self.ROUTING_KEY,
        )
