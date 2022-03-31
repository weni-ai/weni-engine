from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers

from rest_framework.exceptions import PermissionDenied

from connect.api.v1 import fields
from connect.api.v1.fields import TextField
from connect.api.v1.project.validators import CanContributeInOrganizationValidator
from connect.celery import app as celery_app
from connect.common import tasks
from connect.common.models import (
    Service, Project, Organization, RequestPermissionProject, ProjectRoleLevel, RocketRole, RocketRoleLevel
)


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = [
            "uuid",
            "name",
            "organization",
            "timezone",
            "date_format",
            "flow_organization",
            "inteligence_count",
            "flow_count",
            "contact_count",
            "total_contact_count",
            "menu",
            "created_at",
        ]
        ref_name = None

    uuid = serializers.UUIDField(style={"show": False}, read_only=True)
    name = serializers.CharField(max_length=40, required=True)
    organization = serializers.PrimaryKeyRelatedField(
        queryset=Organization.objects,
        validators=[CanContributeInOrganizationValidator()],
        required=True,
        style={"show": False},
    )
    timezone = fields.TimezoneField(required=True)
    menu = serializers.SerializerMethodField()
    flow_organization = serializers.UUIDField(style={"show": False}, read_only=True)
    inteligence_count = serializers.IntegerField(read_only=True)
    flow_count = serializers.IntegerField(read_only=True)
    contact_count = serializers.IntegerField(read_only=True)
    total_contact_count = serializers.IntegerField(read_only=True)
    created_at = serializers.DateTimeField(
        required=False, read_only=True, style={"show": False}
    )

    def get_menu(self, obj):
        return {
            "inteligence": settings.INTELIGENCE_URL,
            "flows": settings.FLOWS_URL,
            "integrations": settings.INTEGRATIONS_URL,
            "chat": list(
                obj.service_status.filter(
                    service__service_type=Service.SERVICE_TYPE_CHAT
                ).values_list("service__url", flat=True)
            ),
        }

    def create(self, validated_data):
        task = tasks.create_project.delay(  # pragma: no cover
            validated_data.get("name"),
            self.context["request"].user.email,
            str(validated_data.get("timezone")),
        )
        if not settings.TESTING:
            task.wait()  # pragma: no cover

        project = task.result

        validated_data.update({"flow_organization": project.get("uuid")})
        instance = super().create(validated_data)

        instance.send_email_create_project(
            first_name=self.context["request"].user.first_name,
            email=self.context["request"].user.email,
        )

        return instance

    def update(self, instance, validated_data):
        name = validated_data.get("name", instance.name)
        celery_app.send_task(
            "update_project",
            args=[instance.flow_organization, name],
        )
        return super().update(instance, validated_data)


class ProjectSearchSerializer(serializers.Serializer):
    text = TextField(label=_("Text Search"), max_length=600)
    project_uuid = serializers.PrimaryKeyRelatedField(
        label=_("Project UUID"),
        queryset=Project.objects,
        required=True,
        style={"show": False},
    )


class RequestPermissionProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = RequestPermissionProject
        fields = ["email", "project", "role", "created_by"]
        ref_name = None

    email = serializers.EmailField(max_length=254, required=True)
    project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects,
        style={"show": False},
        required=True,
    )
    created_by = serializers.HiddenField(
        default=serializers.CurrentUserDefault(), style={"show": False}
    )

    def validate(self, attrs):
        if attrs.get("role") == ProjectRoleLevel.NOTHING.value:
            raise PermissionDenied(_("You cannot set user role 0"))
        return attrs

class RequestRocketPermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RequestRocketPermission
        fields = ["email", "project", "role", "created_by"]

    email = serializers.EmailField(max_length=254, required=True)
    project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects,
        style={"show": False},
        required=True,
    )
    created_by = serializers.HiddenField(
        default=serializers.CurrentUserDefault(), style={"show": False}
    )
    
    def validate(self, attrs):
        if(attrs.get('role') == RocketRole().NOT_SETTED.value):
            raise PermissionDenied(_("You cannot set user role 0"))
        return attrs