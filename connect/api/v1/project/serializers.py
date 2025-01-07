import json
import logging
import uuid
import re

from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError

from connect.api.v1.internal.chats.chats_rest_client import ChatsRESTClient
from connect.api.v1 import fields
from connect.api.v1.fields import TextField
from connect.api.v1.internal.flows.flows_rest_client import FlowsRESTClient
from ..internal.intelligence.intelligence_rest_client import IntelligenceRESTClient
from connect.api.v1.project.validators import CanContributeInOrganizationValidator
from connect.common import tasks
from connect.common.models import (
    ChatsRole,
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
    ProjectRole,
    TemplateProject,
    RequestChatsPermission,
    ChatsAuthorization,
)
from connect.usecases.project.update_project import UpdateProjectUseCase

logger = logging.getLogger(__name__)


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
            "project_type",
            "flow_uuid",
            "first_access",
            "wa_demo_token",
            "redirect_url",
            "description",
            "project_type",
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
    description = serializers.CharField(max_length=1000, required=False)
    authorizations = serializers.SerializerMethodField(style={"show": False})
    pending_authorizations = serializers.SerializerMethodField(style={"show": False})
    authorization = serializers.SerializerMethodField(style={"show": False})
    last_opened_on = serializers.SerializerMethodField()
    flow_uuid = serializers.SerializerMethodField()
    first_access = serializers.SerializerMethodField()
    wa_demo_token = serializers.SerializerMethodField()
    redirect_url = serializers.SerializerMethodField()

    def get_flow_uuid(self, obj):
        if obj.is_template and obj.template_project.exists():
            template = obj.template_project.filter(flow_uuid__isnull=False, wa_demo_token__isnull=False, redirect_url__isnull=False).first()
            if template:
                return template.flow_uuid
            ...
        ...

    def get_first_access(self, obj):
        if obj.is_template and obj.template_project.exists():
            user = self.context["request"].user
            email = user.email
            authorization = obj.get_user_authorization(user)

            try:
                template = obj.template_project.get(authorization__user__email=email)
                return template.first_access
            except TemplateProject.DoesNotExist:
                template_project = obj.template_project.filter(wa_demo_token__isnull=False, redirect_url__isnull=False).first()
                template = obj.template_project.create(
                    wa_demo_token=template_project.wa_demo_token,
                    redirect_url=template_project.redirect_url,
                    authorization=authorization
                )
        ...

    def get_wa_demo_token(self, obj):
        if obj.is_template and obj.template_project.exists():
            template = obj.template_project.filter(flow_uuid__isnull=False, wa_demo_token__isnull=False, redirect_url__isnull=False).first()
            if template:
                return template.wa_demo_token
            ...
        ...

    def get_redirect_url(self, obj):
        if obj.is_template and obj.template_project.exists():
            template = obj.template_project.filter(flow_uuid__isnull=False, wa_demo_token__isnull=False, redirect_url__isnull=False).first()
            if template:
                return template.redirect_url
            ...
        ...

    def get_menu(self, obj):
        chats_formatted_url = settings.CHATS_URL + "loginexternal/{{token}}/"
        return {
            "inteligence": settings.INTELIGENCE_URL,
            "flows": settings.FLOWS_URL,
            "integrations": settings.INTEGRATIONS_URL,
            "chats": chats_formatted_url,
            "chat": list(
                obj.service_status.filter(
                    service__service_type=Service.SERVICE_TYPE_CHAT
                ).values_list("service__url", flat=True)
            ),
        }

    def create(self, validated_data):
        user = self.context["request"].user

        flow_instance = FlowsRESTClient()

        project = flow_instance.create_project(
            project_name=validated_data.get("name"),
            user_email=user.email,
            project_timezone=validated_data.get("timezone"),
        )

        validated_data.update(
            {
                "flow_organization": project.get("uuid"),
                "created_by": user
            }
        )
        instance = super().create(validated_data)

        return instance

    def update(self, instance, validated_data):
        updated_instance = super().update(instance, validated_data)
        user = self.context["request"].user
        UpdateProjectUseCase().send_updated_project(instance, user.email)
        return updated_instance

    def get_authorizations(self, obj):
        exclude_roles = [ProjectRole.SUPPORT.value]
        queryset = obj.project_authorizations.exclude(role__in=exclude_roles)
        response = dict(
            count=queryset.count(),
            users=[]
        )
        for i in queryset:
            chats_role = None
            if i.rocket_authorization:
                chats_role = i.rocket_authorization.role
            elif i.chats_authorization:
                chats_role = i.chats_authorization.role
            response['users'].append(
                dict(
                    username=i.user.username,
                    email=i.user.email,
                    first_name=i.user.first_name,
                    last_name=i.user.last_name,
                    project_role=i.role,
                    photo_user=i.user.photo_url,
                    chats_role=chats_role,
                )
            )
        return response

    def get_pending_authorizations(self, obj):
        response = {
            "count": obj.requestpermissionproject_set.count(),
            "users": [],
        }
        for i in obj.requestpermissionproject_set.all():
            rocket_authorization = RequestRocketPermission.objects.filter(email=i.email)
            chats_authorization = RequestChatsPermission.objects.filter(email=i.email)
            chats_role = None
            if(len(rocket_authorization) > 0):
                rocket_authorization = rocket_authorization.first()
                chats_role = rocket_authorization.role

            if len(chats_authorization) > 0:
                chats_authorization = chats_authorization.first()
                chats_role = chats_authorization.role

            response["users"].append(
                dict(
                    email=i.email,
                    project_role=i.role,
                    created_by=i.created_by.email,
                    chats_role=chats_role
                )
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


class ChatsAuthorizationSerializer(serializers.ModelSerializer):
    model = ChatsAuthorization
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

        email = attrs.get("email")

        if ' ' in email:
            raise ValidationError(
                _("Email field cannot have spaces")
            )

        if bool(re.match('[A-Z]', email)):
            raise ValidationError(
                _("Email field cannot have uppercase characters")
            )

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
            "chats_role",
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
    chats_role = serializers.SerializerMethodField()

    def get_chats_role(self, obj):
        if obj.rocket_authorization:
            return dict(
                role=obj.rocket_authorization.role,
                created_at=obj.created_at,
            )
        if obj.chats_authorization:
            return dict(
                role=obj.chats_authorization.role,
                created_at=obj.chats_authorization.created_at,
            )
        return None


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


class RequestChatsPermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RequestChatsPermission
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
        if attrs.get("role") == ChatsRole.NOT_SETTED.value:
            raise PermissionDenied(_("You cannot set user role 0"))
        return attrs


class ReleaseChannelSerializer(serializers.Serializer):
    channel_uuid = serializers.CharField(required=True)
    user = serializers.CharField(required=True)


class ListChannelSerializer(serializers.Serializer):
    channel_data = serializers.SerializerMethodField()

    def get_channel_data(self, obj):
        task = tasks.list_channels(
            project_uuid=str(obj.uuid),
            channel_type=self.context["channel_type"],
        )
        return dict(project_uuid=obj.uuid, channels=task)


class CreateWACChannelSerializer(serializers.Serializer):
    user = serializers.CharField(required=True)
    project_uuid = serializers.CharField(required=True)
    config = serializers.JSONField(required=True)
    phone_number_id = serializers.CharField(required=True)


class CreateChannelSerializer(serializers.Serializer):
    user = serializers.CharField(required=True)
    project_uuid = serializers.CharField(required=True)
    data = serializers.JSONField(required=True)
    channeltype_code = serializers.CharField(required=True)


class DestroyClassifierSerializer(serializers.Serializer):

    uuid = serializers.CharField(required=True)
    user_email = serializers.CharField(required=True)


class RetrieveClassifierSerializer(serializers.Serializer):
    uuid = serializers.CharField(required=True)


class CreateClassifierSerializer(serializers.Serializer):
    name = serializers.CharField(required=True)
    access_token = serializers.CharField(required=True)
    user = serializers.CharField(write_only=True)
    project_uuid = serializers.UUIDField(write_only=True)


class ClassifierSerializer(serializers.Serializer):
    project_uuid = serializers.UUIDField()

    def validate_project_uuid(self, value):
        try:
            Project.objects.get(uuid=value)
        except Project.DoesNotExist:
            raise serializers.ValidationError("This project does not exist")
        return value


class TemplateProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = TemplateProject
        fields = [
            "uuid",
            "project",
            "wa_demo_token",
            "classifier_uuid",
            "first_access",
            "authorization",
            "redirect_url",
            "user",
        ]

    wa_demo_token = serializers.CharField(required=False)
    classifier_uuid = serializers.UUIDField(style={"show": False}, required=False)
    first_access = serializers.BooleanField(default=True)
    authorization = serializers.PrimaryKeyRelatedField(
        queryset=ProjectAuthorization.objects,
        required=True,
        style={"show": False},
    )
    project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects,
        required=True,
        style={"show": False},
    )
    user = serializers.SerializerMethodField()

    def get_user(self, obj):
        return obj.authorization.user.email

    def create(self, validated_data, request):
        data = {}
        project = validated_data.get("project")

        authorization = project.get_user_authorization(request.user)

        if authorization.role == 0:
            data.update(
                {
                    "data": {"message": "Project authorization not setted"},
                    "status": "FAILED"
                }
            )
            return data

        # Create template project model
        template = project.template_project.create(authorization=authorization)

        # Get AI access token
        if not settings.TESTING:
            intelligence_client = IntelligenceRESTClient()
            try:
                repository_uuid = settings.REPOSITORY_IDS.get(project.template_type)
                access_token = intelligence_client.get_access_token(request.user.email, repository_uuid)
            except Exception as error:
                logger.error(f" REPOSITORY IDS {error}")
                template.delete()
                data.update(
                    {
                        "data": {"message": "Could not get access token"},
                        "status": "FAILED"
                    }
                )
                return data
        else:
            access_token = str(uuid.uuid4())

        # Create classifier
        if not settings.TESTING:
            try:
                classifier_uuid = tasks.create_classifier(
                    project_uuid=str(project.flow_organization),
                    user_email=request.user.email,
                    classifier_name="Farewell & Greetings" if project.template_type == Project.TYPE_LEAD_CAPTURE else "Binary Answers",
                    access_token=access_token,
                ).get("uuid")
            except Exception as error:
                logger.error(f"CREATE CLASSIFIER {error}")
                template.delete()
                data.update(
                    {
                        "message": "Could not create classifier",
                        "status": "FAILED"
                    }
                )
                return data
        else:
            classifier_uuid = uuid.uuid4()

    # Create Flow and Ticketer
        if not settings.TESTING and not settings.USE_EDA:
            rest_client = FlowsRESTClient()
            try:
                is_support = project.template_type == Project.TYPE_SUPPORT
                if is_support:
                    chats_client = ChatsRESTClient()
                    chats_response = chats_client.create_chat_project(
                        project_uuid=str(project.uuid),
                        project_name=project.name,
                        date_format=project.date_format,
                        timezone=str(project.timezone),
                        is_template=True,
                        user_email=project.created_by.email
                    )
                    chats_response = json.loads(chats_response.text)
                flows = rest_client.create_flows(
                    str(project.uuid),
                    str(classifier_uuid),
                    project.template_type,
                    ticketer=chats_response.get("ticketer") if is_support else None,
                    queue=chats_response.get("queue") if is_support else None,
                )
                if flows.get("status") == 201:
                    flows = json.loads(flows.get("data"))
            except Exception as error:
                logger.error(error)
                template.delete()
                data.update(
                    {
                        "message": "Could not create flow",
                        "status": "FAILED"
                    }
                )
                return data
        else:
            flows = {"uuid": uuid.uuid4()}

        flow_uuid = flows.get("uuid")

        template.classifier_uuid = classifier_uuid
        template.flow_uuid = flow_uuid

        wa_demo_token = "wa-demo-12345"
        redirect_url = "https://wa.me/5582123456?text=wa-demo-12345"
        template.wa_demo_token = wa_demo_token
        template.redirect_url = redirect_url
        template.save(update_fields=["classifier_uuid", "flow_uuid", "wa_demo_token", "redirect_url"])

        data = {
            "first_access": template.first_access,
            "flow_uuid": str(template.flow_uuid),
            "project_type": "template",
            "wa_demo_token": template.wa_demo_token,
            "redirect_url": redirect_url,
        }

        return data


class UserAPITokenSerializer(serializers.Serializer):
    user = serializers.EmailField(required=True)
    project_uuid = serializers.UUIDField(required=True)

    def validate_project_uuid(self, value):
        try:
            Project.objects.get(uuid=value)
        except Project.DoesNotExist:
            raise serializers.ValidationError("This project does not exist")
        return value
