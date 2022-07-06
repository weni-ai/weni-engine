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
    ProjectAuthorization,
    RocketAuthorization,
    Service,
    Project,
    Organization,
    RequestPermissionProject,
    ProjectRoleLevel,
    RocketRole,
    RequestRocketPermission,
    OpenedProject,
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
            "authorizations",
            "pending_authorizations",
            "authorization",
            "last_opened_on",
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
    authorizations = serializers.SerializerMethodField(style={"show": False})
    pending_authorizations = serializers.SerializerMethodField(style={"show": False})
    authorization = serializers.SerializerMethodField(style={"show": False})
    last_opened_on = serializers.SerializerMethodField()

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

        return instance

    def update(self, instance, validated_data):
        name = validated_data.get("name", instance.name)
        celery_app.send_task(
            "update_project",
            args=[instance.flow_organization, name],
        )
        return super().update(instance, validated_data)

    def get_authorizations(self, obj):
        return {
            "count": obj.project_authorizations.count(),
            "users": [
                {
                    "username": i.user.username,
                    "email": i.user.email,
                    "first_name": i.user.first_name,
                    "last_name": i.user.last_name,
                    "project_role": i.role,
                    "photo_user": i.user.photo_url,
                    "rocket_authorization": i.rocket_authorization.role
                    if i.rocket_authorization
                    else None,
                }
                for i in obj.project_authorizations.all()
            ],
        }

    def get_pending_authorizations(self, obj):
        response = {
            "count": obj.requestpermissionproject_set.count(),
            "users": [],
        }
        for i in obj.requestpermissionproject_set.all():
            rocket_authorization = RequestRocketPermission.objects.filter(email=i.email)
            rocket_role = None
            if(len(rocket_authorization) > 0):
                rocket_authorization = rocket_authorization.first()
                rocket_role = rocket_authorization.role

            response["users"].append(
                {
                    "email": i.email,
                    "project_role": i.role,
                    "created_by": i.created_by.email,
                    "rocket_authorization": rocket_role
                }
            )
        return response

    def get_authorization(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None

        data = ProjectAuthorizationSerializer(
            obj.get_user_authorization(request.user)
        ).data
        return data

    def get_last_opened_on(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None
        opened = OpenedProject.objects.filter(user__email=request.user, project=obj.uuid)
        response = None
        if opened.exists():
            opened = opened.first()
            response = opened.day
        return response


class RocketAuthorizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = RocketAuthorization
        fields = ["role", "created_at"]


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


class ProjectAuthorizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectAuthorization
        fields = [
            "uuid",
            "user",
            "user__id",
            "user__username",
            "user__email",
            "user__photo",
            "project",
            "rocket_authorization",
            "role",
            "created_at",
        ]

        read_only = ["user", "user__username", "organization", "role", "created_at"]

    user__id = serializers.IntegerField(source="user.id", read_only=True)
    user__username = serializers.SlugRelatedField(
        source="user", slug_field="username", read_only=True
    )
    user__email = serializers.EmailField(
        source="user.email", label=_("Email"), read_only=True
    )
    user__photo = serializers.ImageField(
        source="user.photo", label=_("User photo"), read_only=True
    )
    rocket_authorization = RocketAuthorizationSerializer()


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
        if attrs.get("role") == RocketRole.NOT_SETTED.value:
            raise PermissionDenied(_("You cannot set user role 0"))
        return attrs


class ReleaseChannelSerializer(serializers.Serializer):
    channel_uuid = serializers.CharField(required=True)
    user = serializers.CharField(required=True)


class ListChannelSerializer(serializers.Serializer):
    channel_data = serializers.SerializerMethodField()

    def get_channel_data(self, obj):
        task = tasks.list_channels.delay(
            project_uuid=str(obj.flow_organization),
            channel_type=self.context["channel_type"],
        )
        task.wait()
        return dict(project_uuid=obj.uuid, channels=task.result)


class CreateWACChannelSerializer(serializers.Serializer):
    user = serializers.CharField(required=True)
    project_uuid = serializers.CharField(required=True)
    config = serializers.CharField(required=True)
    phone_number_id = serializers.CharField(required=True)


class CreateChannelSerializer(serializers.Serializer):
    user = serializers.CharField(required=True)
    project_uuid = serializers.CharField(required=True)
    data = serializers.JSONField(required=True)
    channeltype_code = serializers.CharField(required=True)
