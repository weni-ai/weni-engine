from rest_framework.response import Response
from rest_framework import status
from rest_framework import views
from rest_framework.viewsets import GenericViewSet
from rest_framework.mixins import CreateModelMixin
from connect.api.v2.commerce.permissions import CanCommunicateInternally
from connect.api.v2.commerce.serializers import CommerceSerializer
from connect.api.v2.paginations import CustomCursorPagination
from connect.common.models import Organization, Project, ProjectAuthorization, OrganizationRole
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
        data = request.data
        project = Project.objects.filter(vtex_account=data.get("vtex_account"))
        print(f"request data: {data}")
        if project.count() > 0:
            project = project.first()
        else:
            return Response(
                {
                    "message": f"Project with vtex_account {data.get('vtex_account')} doesn't exists!",
                    "data": {
                        "has_project": False
                    }
                }, status=status.HTTP_200_OK)

        organization = project.organization
        print(f"project: {project.__dict__}")
        permission = ProjectAuthorization.objects.filter(project=project, user__email=data.get("user_email"))

        if permission.count() > 0:
            permission = permission.first()
        else:
            try:
                user = User.objects.get(email=data.get("user_email"))
            except Exception as e:
                print(f"error: {e}")
                user_dto = KeycloakUserDTO(
                    email=data.get("user_email"),
                    company_name=project.organization.name,
                )
                print(f"user dto: {user_dto}")
                create_keycloak_user_use_case = CreateKeycloakUserUseCase(user_dto)
                user_info = create_keycloak_user_use_case.execute()
                user = user_info.get("user")
            organization.authorizations.create(
                user=user, role=OrganizationRole.ADMIN.value
            )
        return Response(
            {
                "message": f"Project {project.name} exists and user {permission.user.email} has permission",
                "data": {
                    "project_uuid": project.uuid,
                    "has_project": True
                }
            }, status=status.HTTP_200_OK)
