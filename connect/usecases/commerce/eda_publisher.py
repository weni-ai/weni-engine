from typing import Dict, List

from django.conf import settings

from connect.authentication.models import User
from connect.common.models import Organization, Project
from connect.internals.event_driven.producer.rabbitmq_publisher import RabbitmqPublisher


class CommerceEDAPublisher:
    """Handles EDA event publishing for commerce project creation.

    Resolves its own publisher based on settings, following the same
    pattern as ProjectEDAPublisher.
    """

    def __init__(self):
        if settings.USE_EDA and not settings.TESTING:
            self._publisher = RabbitmqPublisher()
        else:
            self._publisher = None

    def publish_org_created(self, organization: Organization, user: User) -> None:
        if not self._publisher:
            return

        body = self._build_org_body(organization, user)
        self._publisher.send_message(body=body, exchange="orgs.topic", routing_key="")

    def publish_project_created(self, project: Project) -> None:
        if not self._publisher:
            return

        body = self._build_project_body(project)
        self._publisher.send_message(
            body=body, exchange="projects.topic", routing_key=""
        )

    def _build_org_body(self, organization: Organization, user: User) -> Dict:
        return {
            "uuid": str(organization.uuid),
            "name": organization.name,
            "authorizations": self._get_contributor_authorizations(organization),
            "user_email": user.email,
        }

    def _build_project_body(self, project: Project) -> Dict:
        return {
            "uuid": str(project.uuid),
            "name": project.name,
            "is_template": project.is_template,
            "user_email": project.created_by.email if project.created_by else None,
            "date_format": project.date_format,
            "template_type_uuid": (
                str(project.project_template_type.uuid)
                if project.project_template_type
                else None
            ),
            "timezone": "America/Sao_Paulo",
            "organization_id": project.organization.inteligence_organization,
            "extra_fields": {},
            "authorizations": self._get_contributor_authorizations(
                project.organization
            ),
            "description": "Commerce project",
            "organization_uuid": str(project.organization.uuid),
            "brain_on": True,
            "project_type": project.project_type.value,
            "vtex_account": project.vtex_account,
            "language": project.language,
        }

    @staticmethod
    def _get_contributor_authorizations(organization: Organization) -> List[Dict]:
        return [
            {"user_email": auth.user.email, "role": auth.role}
            for auth in organization.authorizations.all()
            if auth.can_contribute
        ]
