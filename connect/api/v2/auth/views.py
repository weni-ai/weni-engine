from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from connect.api.v2.auth.serializers import KeycloakAuthSerializer
from connect.usecases.keycloak.authenticate import KeycloakAuthenticateUseCase
from connect.middleware import WeniOIDCAuthentication
from connect.common.models import ProjectAuthorization


class KeycloakAuthView(views.APIView):
    def post(self, request):
        serializer = KeycloakAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            use_case = KeycloakAuthenticateUseCase()
            tokens = use_case.execute(
                username=serializer.validated_data["user"],
                password=serializer.validated_data["password"],
            )
            return Response(tokens, status=status.HTTP_200_OK)

        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ProjectAuthView(views.APIView):
    authentication_classes = [WeniOIDCAuthentication]
    permission_classes = [IsAuthenticated]

    def get_available_roles(self):
        return {choice[0]: choice[1] for choice in ProjectAuthorization.ROLE_CHOICES}

    def get(self, request, project_uuid: str = None):
        try:
            project_authorization = request.user.project_authorizations_user.get(project__uuid=project_uuid)
        except ProjectAuthorization.DoesNotExist:
            return Response({"error": "Project authorization not found"}, status=status.HTTP_404_NOT_FOUND)

        response = {
            "user": request.user.email,
            "project_authorization": project_authorization.role,
            "available_roles": self.get_available_roles()
        }
        return Response(response)
