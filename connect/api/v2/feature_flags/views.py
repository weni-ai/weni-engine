import logging

from rest_framework import views, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from connect.api.v1.project.permissions import ProjectHasPermission
from connect.api.v2.feature_flags.serializers import FeatureFlagsRequestSerializer
from connect.common.models import Project

from weni_feature_flags.services import FeatureFlagsService

logger = logging.getLogger(__name__)


class FeatureFlagsAPIView(views.APIView):
    """
    API View for retrieving active feature flags for a user and project.

    This endpoint centralizes feature flag requests from all frontend projects,
    using GrowthBook configuration that supports all projects (not filtered by a single project).
    """

    permission_classes = [IsAuthenticated, ProjectHasPermission]

    def get(self, request):
        """
        Get active feature flags for the authenticated user and specified project.

        Query Parameters:
            - project_uuid (required): UUID of the project

        Returns:
            JSON response with active feature flags in format:
            {
                "features": [
                    "feature-1",
                    "feature-2",
                    "feature-3",
                    ...
                ]
            }
        """
        serializer = FeatureFlagsRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        project_uuid = serializer.validated_data.get("project_uuid")

        try:
            project = Project.objects.get(uuid=project_uuid)
        except Project.DoesNotExist:
            raise ValidationError({"project_uuid": "Project not found"})

        # Check if user has permission to access this project
        self.check_object_permissions(request, project)

        # Get user email from authenticated user
        user_email = request.user.email

        # Prepare attributes for GrowthBook evaluation
        attributes = {
            "userEmail": user_email,
            "projectUUID": str(project_uuid),
        }

        try:
            service = FeatureFlagsService()
            active_features = service.get_active_feature_flags_for_attributes(
                attributes
            )

            return Response({"features": active_features}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(
                "Failed to retrieve feature flags for user %s and project %s: %s",
                user_email,
                project_uuid,
                str(e),
                exc_info=True,
            )
            return Response(
                {"error": "Failed to retrieve feature flags", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
