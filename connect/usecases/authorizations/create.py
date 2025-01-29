from typing import Union
from django.db.models import QuerySet
from connect.common.models import (
    Organization,
    User,
    Project,
    OrganizationAuthorization,
    RequestPermissionProject,
    ProjectAuthorization,
)
from connect.usecases.authorizations.usecase import AuthorizationUseCase
from connect.usecases.organizations.retrieve import RetrieveOrganizationUseCase
from connect.usecases.authorizations.dto import (
    CreateAuthorizationDTO,
    CreateProjectAuthorizationDTO,
)
from connect.usecases.users.retrieve import RetrieveUserUseCase
from connect.usecases.users.exceptions import UserDoesNotExist


class CreateAuthorizationUseCase(AuthorizationUseCase):
    def create_organization_authorization(
        self, auth_dto: CreateAuthorizationDTO, user: User, org: Organization
    ) -> OrganizationAuthorization:
        authorization: OrganizationAuthorization = org.authorizations.create(
            user=user, role=auth_dto.role, has_2fa=user.has_2fa
        )

        if self.publish_message:
            self.publish_organization_authorization_message(
                action="create",
                org_uuid=str(org.uuid),
                user_email=user.email,
                role=authorization.role,
                org_intelligence=org.inteligence_organization,
            )
        return authorization

    def create_project_authorization(
        self,
        project: Project,
        user: User,
        role: int,
        org_auth: OrganizationAuthorization,
    ) -> ProjectAuthorization:
        try:
            project_auth: ProjectAuthorization = project.project_authorizations.get(
                user=user
            )
            project_auth.role = role
            project_auth.save()
            action = "update"

        except ProjectAuthorization.DoesNotExist:
            action = "create"
            project_auth: ProjectAuthorization = project.project_authorizations.create(
                user=user, organization_authorization=org_auth, role=role
            )

        if self.publish_message:
            print(action)
            self.publish_project_authorization_message(
                action=action,
                project_uuid=str(project.uuid),
                user_email=user.email,
                role=project_auth.role,
            )

        return project_auth

    def create_authorization(
        self, auth_dto: CreateAuthorizationDTO
    ) -> OrganizationAuthorization:

        user: User = RetrieveUserUseCase().get_user_by_email(email=auth_dto.user_email)
        org: Organization = RetrieveOrganizationUseCase().get_organization_by_uuid(
            org_uuid=auth_dto.org_uuid
        )

        org_auth = self.create_organization_authorization(
            auth_dto,
            org=org,
            user=user,
        )

        projects: QuerySet[Project] = org_auth.organization.project.all()

        if org_auth.can_contribute:
            for project in projects:
                self.create_project_authorization(
                    project=project,
                    user=user,
                    role=org_auth.role,
                    org_auth=org_auth,
                )
        return org_auth

    def create_authorization_for_a_single_project(
        self, auth_dto: CreateProjectAuthorizationDTO
    ) -> Union[ProjectAuthorization, RequestPermissionProject]:
        org: Organization = (
            RetrieveOrganizationUseCase().get_organization_by_project_uuid(
                project_uuid=auth_dto.project_uuid
            )
        )
        project: Project = org.project.get(uuid=auth_dto.project_uuid)

        try:
            user: User = RetrieveUserUseCase().get_user_by_email(
                email=auth_dto.user_email
            )
        except UserDoesNotExist:
            return self.create_request_permission_for_user_that_dosent_exist(
                project=project, auth_dto=auth_dto
            )

        try:
            org_auth = org.authorizations.get(user=user)
            project_auth = self.create_project_authorization(
                project=project,
                user=user,
                role=auth_dto.role,
                org_auth=org_auth,
            )
            project.send_email_invite_project(user.email)
            return project_auth

        except OrganizationAuthorization.DoesNotExist:
            create_auth_dto = CreateAuthorizationDTO(
                user_email=auth_dto.user_email, org_uuid=str(org.uuid), role=1
            )
            org_auth = self.create_organization_authorization(
                create_auth_dto, user, org
            )

            project_auth = self.create_project_authorization(
                project=project,
                user=user,
                role=auth_dto.role,
                org_auth=org_auth,
            )
            project.send_email_invite_project(user.email)
            return project_auth

    def create_request_permission_for_user_that_dosent_exist(
        self, project: Project, auth_dto: CreateProjectAuthorizationDTO
    ):
        created_by_user: User = RetrieveUserUseCase().get_user_by_email(
            email=auth_dto.created_by_email
        )
        try:
            request_permission = RequestPermissionProject.objects.get(
                email=auth_dto.user_email, project=project
            )
            request_permission.role = auth_dto.role
            request_permission.created_by = created_by_user
            request_permission.save()
            project.send_email_invite_project(request_permission.email)
            return request_permission

        except RequestPermissionProject.DoesNotExist:
            request_permission = RequestPermissionProject.objects.create(
                email=auth_dto.user_email,
                project=project,
                role=auth_dto.role,
                created_by=created_by_user,
            )
            project.send_email_invite_project(request_permission.email)
            return request_permission
