from typing import Dict

from connect.common.models import (
    OrganizationRole,
    ProjectRole,
)


class MockRabbitMQPublisher:
    def send_message(self, body: Dict, exchange: str, routing_key: str):
        msg = f"Sending {body} to {exchange}"
        if routing_key:
            msg += f":{routing_key}"
        print(msg)
        return


class AuthorizationUseCase:
    organization_permission_mapper = {
        OrganizationRole.VIEWER.value: ProjectRole.VIEWER.value,
        OrganizationRole.ADMIN.value: ProjectRole.MODERATOR.value,
        OrganizationRole.CONTRIBUTOR.value: ProjectRole.CONTRIBUTOR.value,
        OrganizationRole.SUPPORT.value: ProjectRole.SUPPORT.value,
    }

    def __init__(self, message_publisher = MockRabbitMQPublisher(), publish_message: bool = True) -> None:
        self.message_publisher = message_publisher
        self.publish_message = publish_message

    def publish_organization_authorization_message(
            self,
            action: str,
            org_uuid: str,
            user_email: str,
            role: int,
            org_intelligence: int,
        ) -> None:

        message_body = {
            "action": action,
            "organization_uuid": org_uuid,
            "user_email": user_email,
            "role": role,
            "org_intelligence": org_intelligence
        }
        self.message_publisher.send_message(message_body, exchange="orgs-auths.topic", routing_key="")

    def publish_project_authorization_message(
            self,
            action: str,
            project_uuid: str,
            user_email: str,
            role: int,
    ) -> None:
        message_body = {
            "action": action,
            "project": project_uuid,
            "user": user_email,
            "role": role
        }
        self.message_publisher.send_message(message_body, exchange="project-auths.topic", routing_key="")
