from django.db.models import QuerySet
from connect.common.models import (
    Organization,
    User,
    Project,
    OrganizationAuthorization,
    ProjectAuthorization,
)
from connect.usecases.authorizations.dto import UpdateAuthorizationDTO
from connect.usecases.organizations.retrieve import RetrieveOrganizationUseCase
from connect.usecases.authorizations.usecase import AuthorizationUseCase
from connect.usecases.users.retrieve import RetrieveUserUseCase

from rest_framework.exceptions import PermissionDenied


class UpdateAuthorizationUseCase(AuthorizationUseCase):

    def update_organization_authorization(self, auth_dto: UpdateAuthorizationDTO, user: User, org: Organization):
        authorization: OrganizationAuthorization = org.authorizations.get(user=user)

        authorization.role = auth_dto.role
        authorization.save(update_fields=["role"])
        authorization.refresh_from_db()

        if self.publish_message:
            self.publish_organization_authorization_message(
                action="update",
                org_uuid=str(org.uuid),
                user_email=user.email,
                role=authorization.role,
                org_intelligence=org.inteligence_organization
            )

        return authorization

    def update_project_authorization(self, project: Project, user: User, role: int) -> ProjectAuthorization:
        auth = project.project_authorizations.get(user=user)
        auth.role = role
        auth.save(update_fields=["role"])

        if self.publish_message:
            self.publish_project_authorization_message(
                action="update",
                project_uuid=str(project.uuid),
                user_email=user.email,
                role=auth.role,
            )
        return auth

    def update_authorization(self, auth_dto: UpdateAuthorizationDTO) -> OrganizationAuthorization:

        if auth_dto.user_email == auth_dto.request_user:
            raise PermissionDenied("Can't change own permission")

        if auth_dto.user_email:
            user: User = RetrieveUserUseCase().get_user_by_email(email=auth_dto.user_email)
        elif auth_dto.id:
            user: User = RetrieveUserUseCase().get_user_by_id(id=auth_dto.id)

        org: Organization = RetrieveOrganizationUseCase().get_organization_by_uuid(org_uuid=auth_dto.org_uuid)

        org_auth: OrganizationAuthorization = self.update_organization_authorization(auth_dto, user=user, org=org)

        projects: QuerySet[Project] = org_auth.organization.project.all()

        if org_auth.can_contribute:
            project_role = self.organization_permission_mapper.get(org_auth.role)

            for project in projects:
                self.update_project_authorization(
                    project=project,
                    user=user,
                    role=project_role,
                )

        return org_auth
