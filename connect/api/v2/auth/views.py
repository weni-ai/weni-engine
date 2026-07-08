from rest_framework import status, views
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from connect.api.v2.auth.serializers import KeycloakAuthSerializer
from connect.common.models import ProjectAuthorization
from connect.middleware import WeniOIDCAuthentication
from connect.usecases.authorizations.get_project_authorization import (
    GetProjectAuthorizationUseCase,
)
from connect.usecases.keycloak.authenticate import KeycloakAuthenticateUseCase


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


class BaseProjectAuthorizationView(views.APIView):
    authentication_classes = [WeniOIDCAuthentication]
    permission_classes = [IsAuthenticated]

    def get_available_roles(self):
        return {choice[0]: choice[1] for choice in ProjectAuthorization.ROLE_CHOICES}

    def _resolve_target_user_email(self, request: Request) -> str:
        user_email = request.query_params.get("user")

        if user_email is None:
            return request.user.email

        if not request.user.has_perm("authentication.can_communicate_internally"):
            raise PermissionDenied(
                "You do not have permission to access other users' data"
            )

        return user_email

    def _build_response(self, authorization: ProjectAuthorization) -> Response:
        return Response(
            {
                "user": authorization.user.email,
                "project_authorization": authorization.role,
                "available_roles": self.get_available_roles(),
            }
        )


class ProjectAuthView(BaseProjectAuthorizationView):
    def get(self, request: Request, project_uuid: str = None):
        user_email = self._resolve_target_user_email(request)
        authorization = GetProjectAuthorizationUseCase().get_by_project_uuid(
            user_email=user_email, project_uuid=project_uuid
        )
        return self._build_response(authorization)


class VtexAccountProjectAuthView(BaseProjectAuthorizationView):
    def get(self, request: Request, vtex_account: str = None):
        user_email = self._resolve_target_user_email(request)
        authorization = GetProjectAuthorizationUseCase().get_by_vtex_account(
            user_email=user_email, vtex_account=vtex_account
        )
        return self._build_response(authorization)
