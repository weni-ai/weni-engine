from rest_framework.response import Response
from rest_framework import status
from rest_framework import views
from rest_framework.viewsets import GenericViewSet
from rest_framework.mixins import CreateModelMixin
from connect.api.v2.commerce.permissions import CanCommunicateInternally
from connect.api.v2.commerce.serializers import CommerceSerializer
from connect.api.v2.paginations import CustomCursorPagination
from connect.common.models import Organization, Project, ProjectAuthorization, OrganizationRole, RequestPermissionOrganization
from connect.authentication.models import User
from connect.usecases.users.create import CreateKeycloakUserUseCase
from connect.usecases.users.user_dto import KeycloakUserDTO


class CommerceOrganizationViewSet(CreateModelMixin, GenericViewSet):
    queryset = Organization.objects.all()
    serializer_class = CommerceSerializer
    permission_classes = [CanCommunicateInternally]
    lookup_field = "uuid"
    pagination_class = CustomCursorPagination

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.save()

        response = {
            "organization_uuid": str(data.get("organization").uuid),
            "project_uuid": str(data.get("project").uuid),
        }

        return Response(response, status=status.HTTP_201_CREATED)


class CommerceProjectCheckExists(views.APIView):

    permission_classes = [CanCommunicateInternally]

    def get(self, request):
        user_email = request.query_params.get("user_email")
        vtex_account = request.query_params.get("vtex_account")
        project = Project.objects.filter(vtex_account=vtex_account)
        if project.count() > 0:
            project = project.first()
        else:
            return Response(
                {
                    "message": f"Project with vtex_account {vtex_account} doesn't exists!",
                    "data": {
                        "has_project": False
                    }
                }, status=status.HTTP_200_OK)

        organization = project.organization
        permission = ProjectAuthorization.objects.filter(project=project, user__email=user_email)

        if permission.count() > 0:
            permission = permission.first()
        else:
            try:
                user = User.objects.get(email=user_email)
            except Exception as e:
                print(f"error: {e}")
                user_dto = KeycloakUserDTO(
                    email=user_email,
                    company_name=project.organization.name,
                )
                create_keycloak_user_use_case = CreateKeycloakUserUseCase(user_dto)
                user_info = create_keycloak_user_use_case.execute()
                user = user_info.get("user")
                user.send_email_access_password(user_info.get("password"))
            RequestPermissionOrganization.objects.create(
                email=user.email,
                organization=organization,
                role=OrganizationRole.ADMIN.value,
                created_by=user,
            )
        return Response(
            {
                "message": f"Project {project.name} exists and user {user_email} has permission",
                "data": {
                    "project_uuid": project.uuid,
                    "has_project": True
                }
            }, status=status.HTTP_200_OK)
