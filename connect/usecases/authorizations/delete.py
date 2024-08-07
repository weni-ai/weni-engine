from django.db.models import QuerySet
from connect.common.models import (
    Organization,
    User,
    Project,
    OrganizationAuthorization,
    RequestPermissionProject,
    ProjectAuthorization,

)
from connect.usecases.organizations.retrieve import RetrieveOrganizationUseCase
from connect.usecases.users.retrieve import RetrieveUserUseCase

from connect.usecases.authorizations.dto import DeleteAuthorizationDTO, DeleteProjectAuthorizationDTO

from connect.usecases.authorizations.usecase import AuthorizationUseCase


class DeleteAuthorizationUseCase(AuthorizationUseCase):
    def delete_organization_authorization(self, user: User, org: Organization):
        try:
            authorization = org.authorizations.get(user=user)
            authorization.delete()

            if self.publish_message:
                self.publish_organization_authorization_message(
                    action="delete",
                    org_uuid=str(org.uuid),
                    user_email=user.email,
                    role=authorization.role,
                    org_intelligence=org.inteligence_organization
                )
        except OrganizationAuthorization.DoesNotExist:
            print(f"OrganizationAuthorization matching query does not exist: Org {org.uuid} User {user.email}")

    def delete_project_authorization(self, project: Project, user: User, role: int = None):

        authorization = project.project_authorizations.get(user=user)
        authorization.delete()
        
        if not ProjectAuthorization.objects.filter(user=user, organization_authorization=authorization.organization_authorization).exists():
            self.delete_organization_authorization(user=user, org=project.organization)

        if not role:
            role = authorization.role

        if self.publish_message:
            self.publish_project_authorization_message(
                action="delete",
                project_uuid=str(project.uuid),
                user_email=user.email,
                role=role,
            )

    def delete_authorization(self, auth_dto: DeleteAuthorizationDTO):

        if auth_dto.user_email:
            user: User = RetrieveUserUseCase().get_user_by_email(email=auth_dto.user_email)
        elif auth_dto.id:
            user: User = RetrieveUserUseCase().get_user_by_id(id=auth_dto.id)

        org: Organization = RetrieveOrganizationUseCase().get_organization_by_uuid(org_uuid=auth_dto.org_uuid)

        org_auth = org.authorizations.get(user=user)

        projects_uuids: QuerySet = user.project_authorizations_user.all().values_list("project", flat=True)

        for project_uuid in projects_uuids:
            project = Project.objects.get(uuid=project_uuid)
            project_role = self.organization_permission_mapper.get(org_auth.role)
            self.delete_project_authorization(
                project=project,
                user=user,
                role=project_role
            )

        org_auth: OrganizationAuthorization = self.delete_organization_authorization(user=user, org=org)

    def delete_single_project_permission(self, auth_dto: DeleteProjectAuthorizationDTO):
        project = Project.objects.get(uuid=auth_dto.project_uuid)
        try:
            request_auth = RequestPermissionProject.objects.get(email=auth_dto.user_email, project=project)
            request_auth.delete()
        except RequestPermissionProject.DoesNotExist:
            user: User = RetrieveUserUseCase().get_user_by_email(email=auth_dto.user_email)
            self.delete_project_authorization(project=project, user=user)
