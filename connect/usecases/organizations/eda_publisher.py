from typing import Dict, Optional
from uuid import UUID

import pendulum
from django.conf import settings

from connect.internals.event_driven.producer.rabbitmq_publisher import RabbitmqPublisher


class OrganizationEDAPublisher:
    def __init__(self):
        if settings.USE_EDA and not settings.TESTING:
            self.rabbitmq_publisher = RabbitmqPublisher()
        else:
            self.rabbitmq_publisher = None

    def publish_organization_deactivated(self, organization_uuid: UUID, deactivated_at: Optional[pendulum.DateTime] = None) -> None:
        if not self.rabbitmq_publisher:
            return

        if deactivated_at is None:
            deactivated_at = pendulum.now('UTC')

        message_body = {
            "uuid": str(organization_uuid),
            "action": "deactivated",
            "timestamp": deactivated_at.to_iso8601_string(),
            "event_type": "organization_status_changed"
        }

        self.rabbitmq_publisher.send_message(
            body=message_body,
            exchange="orgs.topic",
            routing_key="organization.deactivated"
        )

    def publish_organization_activated(self, organization_uuid: UUID, activated_at: Optional[pendulum.DateTime] = None) -> None:
        if not self.rabbitmq_publisher:
            return

        if activated_at is None:
            activated_at = pendulum.now('UTC')

        message_body = {
            "uuid": str(organization_uuid),
            "action": "activated",
            "timestamp": activated_at.to_iso8601_string(),
            "event_type": "organization_status_changed"
        }

        self.rabbitmq_publisher.send_message(
            body=message_body,
            exchange="orgs.topic",
            routing_key="organization.activated"
        )
