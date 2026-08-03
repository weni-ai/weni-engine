from rest_framework import serializers

from connect.common.models import ProjectMigration
from connect.usecases.project.migration.migrate_project import (
    MODULE_STATUS_ERROR,
    MODULE_STATUS_SUCCESS,
)


class ProjectMigrationCreateSerializer(serializers.Serializer):
    project_uuid = serializers.UUIDField()
    org_to = serializers.UUIDField()


class ProjectMigrationModuleStatusSerializer(serializers.Serializer):
    module = serializers.CharField(max_length=100)
    status = serializers.ChoiceField(
        choices=[MODULE_STATUS_SUCCESS, MODULE_STATUS_ERROR]
    )
    error = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, default=None
    )


class ProjectMigrationSerializer(serializers.ModelSerializer):
    event_id = serializers.UUIDField(source="uuid", read_only=True)
    project_uuid = serializers.UUIDField(source="project_id", read_only=True)

    class Meta:
        model = ProjectMigration
        fields = [
            "event_id",
            "project_uuid",
            "org_from",
            "org_to",
            "status",
            "modules_status",
            "requested_by",
            "published_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
