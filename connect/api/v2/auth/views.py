from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework import status, views
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from connect.api.v2.auth.serializers import KeycloakAuthSerializer, StaffAccessSerializer
from connect.common.models import ProjectAuthorization
from connect.middleware import WeniOIDCAuthentication
from connect.usecases.keycloak.authenticate import KeycloakAuthenticateUseCase
from connect.authentication.models import StaffAccess

User = get_user_model()


class KeycloakAuthView(views.APIView):
    def post(self, request: Request):
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

    def get(self, request: Request, project_uuid: str = None):
        user_email = request.query_params.get("user")

        user = request.user

        if user_email is not None:
            if not request.user.has_perm("authentication.can_communicate_internally"):
                raise PermissionDenied(
                    "You do not have permission to access other users' data"
                )

            user = User.objects.filter(email=user_email).first()

            if user is None:
                raise NotFound("User not found")

        try:
            project_authorization = user.project_authorizations_user.get(
                project__uuid=project_uuid
            )
        except ProjectAuthorization.DoesNotExist:
            raise NotFound("Project authorization not found")

        response = {
            "user": user.email,
            "project_authorization": project_authorization.role,
            "available_roles": self.get_available_roles(),
        }
        return Response(response)


class StaffAccessView(views.APIView):
    def post(self, request: Request, project_uuid: str):
        request.data["project"] = project_uuid

        serializer = StaffAccessSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data['user']
        project = serializer.validated_data['project']
        expires_at = timezone.now() + settings.STAFF_ACCESS_EXPIRATION_HOURS

        access = StaffAccess.objects.grant_access(user, project, expires_at)

        return Response({
            "user": access.user_email,
            "project": access.project_uuid,
            "expires_at": access.expires_at,
        }, status=status.HTTP_201_CREATED)
