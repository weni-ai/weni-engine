from connect.common.models import (
    OrganizationAuthorization,
    Project,
    ProjectAuthorization,
    User,
)

from connect.usecases.project.retrieve import RetrieveProjectUseCase
from connect.usecases.users.retrieve import RetrieveUserUseCase


class ProjectAuthorizationUseCase:

    def create_or_update_authorization(
            self,
            project: Project,
            user: User,
            role: int,
            org_auth: OrganizationAuthorization
        ):
        try:
            authorization = project.project_authorizations.get(user=user)
            authorization.update_role(role)
            authorization.publish_project_authorization_message(action="update")

        except ProjectAuthorization.DoesNotExist:
            authorization = ProjectAuthorization.objects.create(
                user=user,
                project=project,
                organization_authorization=org_auth,
                role=role,
            )
            authorization.publish_project_authorization_message(action="create")
        return authorization

    def create_project_authorization(
        self,
        msg_body
    ) -> ProjectAuthorization:

        from connect.usecases.organizations.retrieve import RetrieveOrganizationUseCase
        from connect.usecases.organization_authorizations.create import CreateOrgAuthUseCase

        role = msg_body.get("role")

        user = RetrieveUserUseCase().get_user_by_email(msg_body.get("user"))
        org = RetrieveOrganizationUseCase().get_organization_by_uuid(msg_body.get("org_uuid"))

        created, org_auth = CreateOrgAuthUseCase()._get_or_create_organization_authorization(
            user=user,
            org=org
        )
        project = RetrieveProjectUseCase().get_project_by_uuid(msg_body.get("project_uuid"))

        project_authorization = self.create_or_update_authorization(
            project=project,
            user=user,
            role=role,
            org_auth=org_auth
        )
        return project_authorization
