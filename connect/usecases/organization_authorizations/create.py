from connect.common.models import (
    Organization,
    OrganizationAuthorization,
    OrganizationRole,
    User,
    ProjectRole,
)
from connect.usecases.users.retrieve import RetrieveUserUseCase
from connect.usecases.organizations.retrieve import RetrieveOrganizationUseCase
from connect.usecases.project_authorizations.create import ProjectAuthorizationUseCase
from typing import Dict, Tuple
from connect.internals.event_driven.producer.rabbitmq_publisher import RabbitmqPublisher


class CreateOrgAuthUseCase:
    def __init__(self, publisher = RabbitmqPublisher) -> None:
        self.publisher = publisher
        self.organization_permission_mapper = {
            OrganizationRole.ADMIN.value: ProjectRole.MODERATOR.value,
            OrganizationRole.CONTRIBUTOR.value: ProjectRole.CONTRIBUTOR.value,
            OrganizationRole.SUPPORT.value: ProjectRole.SUPPORT.value,
        }

    def _get_or_create_organization_authorization(
            self,
            user: User,
            org: Organization,
            role: int = OrganizationRole.VIEWER.value,
            has_2fa: bool = False,
        ) -> Tuple[bool, OrganizationAuthorization]:
        try:
            return (False, org.authorizations.get(user=user))
        except OrganizationAuthorization.DoesNotExist:
            return True, org.authorizations.create(
                user=user, role=role, has_2fa=has_2fa
            )

    def create_organization_authorization(
            self,
            msg_body: Dict,
        ):
        role = msg_body.get("role")

        user = RetrieveUserUseCase().get_user_by_email(email=msg_body.get("user"))
        org = RetrieveOrganizationUseCase().get_organization_by_uuid(msg_body.get("org_uuid"))

        created, authorization = self._get_or_create_organization_authorization(
            user=user,
            org=org,
            role=role,
            has_2fa=user.has_2fa
        )
        action = "create" if created else "update"

        authorization.publish_create_org_authorization_message(self.publisher, action)

        if authorization.can_contribute:
            self.update_project_authorizations(org, user, authorization.role)

        org.send_email_invite_organization(email=user.email)

    def update_project_authorizations(self, org: Organization, user: User, role: int):
        for project in org.project.all():
            project_role = self.organization_permission_mapper.get(role, None)
            msg_body = {
                "user": user.email,
                "org_uuid": str(org.uuid),
                "project_uuid": str(project.uuid),
                "role": project_role,
            }
            ProjectAuthorizationUseCase().create_project_authorization(msg_body)

    def update_organization_authorization(
            self,
            msg_body: Dict
        ) -> OrganizationAuthorization:
        user = RetrieveUserUseCase().get_user_by_email(email=msg_body.get("user"))
        org = RetrieveOrganizationUseCase().get_organization_by_uuid(msg_body.get("org_uuid"))
        role = msg_body.get("role")
        authorization = org.authorizations.get(user=user)
        authorization.role = role
        authorization.save(update_fields=["role"])
        authorization.publish_create_org_authorization_message(self.publisher, "update")

        if authorization.can_contribute:
            self.update_project_authorizations(org, user, authorization.role)
        return authorization
