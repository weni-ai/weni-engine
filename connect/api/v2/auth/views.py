from rest_framework import status, views
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from weni_commons.auth import SessionTokenAuthentication, WeniAuthViewMixin

from connect.api.v2.auth.permissions import (
    TARGET_USER_QUERY_PARAM,
    CanResolveTargetUser,
)
from connect.api.v2.auth.serializers import (
    GetTokenSerializer,
    InvalidateSessionTokenSerializer,
    KeycloakAuthSerializer,
)
from connect.common.models import ProjectAuthorization
from connect.middleware import WeniAuthentication, WeniOIDCAuthentication
from connect.usecases.auth.generate_session_token import (
    GenerateSessionTokenUseCase,
    ProjectAuthorizationNotFound,
)
from connect.usecases.auth.invalidate_session_token import (
    InvalidateSessionTokenUseCase,
    SessionTokenNotFound,
    SessionTokenProjectMismatch,
)
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


class ProjectAuthorizationResponseMixin:
    def get_available_roles(self):
        return {choice[0]: choice[1] for choice in ProjectAuthorization.ROLE_CHOICES}

    def _build_response_data(self, authorization: ProjectAuthorization) -> dict:
        return {
            "user": authorization.user.email,
            "project_authorization": authorization.role,
            "available_roles": self.get_available_roles(),
        }

    def _build_response(self, authorization: ProjectAuthorization) -> Response:
        return Response(self._build_response_data(authorization))


class ProjectAuthView(ProjectAuthorizationResponseMixin, views.APIView):
    authentication_classes = [WeniOIDCAuthentication]
    permission_classes = [IsAuthenticated, CanResolveTargetUser]

    def get(self, request: Request, project_uuid: str = None):
        target_user_email = (
            request.query_params.get(TARGET_USER_QUERY_PARAM) or request.user.email
        )
        authorization = GetProjectAuthorizationUseCase().get_by_project_uuid(
            user_email=target_user_email, project_uuid=project_uuid
        )
        return self._build_response(authorization)


class VtexAccountProjectAuthView(
    WeniAuthViewMixin, ProjectAuthorizationResponseMixin, views.APIView
):
    authentication_classes = [WeniAuthentication]

    def get(self, request: Request, vtex_account: str = None):
        authorization = GetProjectAuthorizationUseCase().get_by_vtex_account(
            user_email=self.auth.user_email, vtex_account=self.auth.vtex_account
        )
        return self._build_response(authorization)

    def _build_response(self, authorization: ProjectAuthorization) -> Response:
        data = self._build_response_data(authorization)
        data["project_uuid"] = str(authorization.project.uuid)
        return Response(data)


class GetTokenView(views.APIView):
    authentication_classes = [WeniOIDCAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, project_uuid: str = None):
        serializer = GetTokenSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        try:
            token_hash = GenerateSessionTokenUseCase().execute(
                project_uuid=project_uuid,
                user=request.user,
                duration=serializer.validated_data["duration"],
            )
        except ProjectAuthorizationNotFound:
            raise NotFound("Project authorization not found")

        return Response({"hash": token_hash}, status=status.HTTP_200_OK)


class InvalidateSessionTokenView(views.APIView):
    authentication_classes = [SessionTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, project_uuid: str = None):
        serializer = InvalidateSessionTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session = request.auth

        try:
            InvalidateSessionTokenUseCase().execute(
                token_hash=serializer.validated_data["hash"],
                requester_project=session.project,
            )
        except SessionTokenNotFound:
            raise NotFound("Session token not found")
        except SessionTokenProjectMismatch:
            raise PermissionDenied("Session token does not belong to this project")

        return Response(status=status.HTTP_204_NO_CONTENT)
