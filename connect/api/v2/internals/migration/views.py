from rest_framework import status, views
from rest_framework.response import Response

from connect.api.v1.internal.permissions import ModuleHasPermission
from connect.api.v2.internals.migration.serializers import (
    ProjectMigrationCreateSerializer,
    ProjectMigrationModuleStatusSerializer,
    ProjectMigrationSerializer,
)
from connect.common.models import ProjectMigration
from connect.usecases.project.exceptions import ProjectMigrationNotFoundError
from connect.usecases.project.migration.migrate_project import MigrateProjectUseCase


class ProjectMigrationCreateView(views.APIView):
    """POST /v2/internals/connect/project-migrations — trigger a project migration."""

    permission_classes = [ModuleHasPermission]

    def post(self, request, **kwargs):
        serializer = ProjectMigrationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        requested_by = getattr(request.user, "email", None)
        migration = MigrateProjectUseCase().execute(
            project_uuid=serializer.validated_data["project_uuid"],
            org_to_uuid=serializer.validated_data["org_to"],
            requested_by=requested_by,
        )
        return Response(
            ProjectMigrationSerializer(migration).data,
            status=status.HTTP_200_OK,
        )


class ProjectMigrationDetailView(views.APIView):
    """GET /v2/internals/connect/project-migrations/<event_id>"""

    permission_classes = [ModuleHasPermission]

    def get(self, request, event_id, **kwargs):
        try:
            migration = ProjectMigration.objects.get(uuid=event_id)
        except ProjectMigration.DoesNotExist:
            raise ProjectMigrationNotFoundError()

        return Response(
            ProjectMigrationSerializer(migration).data,
            status=status.HTTP_200_OK,
        )


class ProjectMigrationStatusView(views.APIView):
    """POST /v2/internals/connect/project-migrations/<event_id>/status"""

    permission_classes = [ModuleHasPermission]

    def post(self, request, event_id, **kwargs):
        serializer = ProjectMigrationModuleStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        migration = MigrateProjectUseCase().register_module_status(
            event_id=event_id,
            module=serializer.validated_data["module"],
            status=serializer.validated_data["status"],
            error=serializer.validated_data.get("error"),
        )
        return Response(
            ProjectMigrationSerializer(migration).data,
            status=status.HTTP_200_OK,
        )


class ProjectMigrationRepublishView(views.APIView):
    """POST /v2/internals/connect/project-migrations/<event_id>/republish"""

    permission_classes = [ModuleHasPermission]

    def post(self, request, event_id, **kwargs):
        migration = MigrateProjectUseCase().republish(event_id=event_id)
        return Response(
            ProjectMigrationSerializer(migration).data,
            status=status.HTTP_200_OK,
        )
