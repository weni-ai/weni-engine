import logging

from django.contrib.auth import get_user_model
from django.conf import settings

from connect.api.v1.internal.chats.chats_rest_client import ChatsRESTClient
from rest_framework import serializers

from rest_framework import status

from connect.api.v1 import fields
from connect.api.v1.internal.flows.flows_rest_client import FlowsRESTClient
from connect.api.v1.project.validators import CanContributeInOrganizationValidator
from connect.api.v1.project.serializers import ProjectAuthorizationSerializer

from connect.celery import app as celery_app
from connect.common.models import (
    ProjectAuthorization,
    Service,
    Project,
    Organization,
    RequestRocketPermission,
    OpenedProject,
    ProjectRole,
    TemplateProject,
    RequestChatsPermission,
)

logger = logging.getLogger(__name__)
User = get_user_model()


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
        ]
        ref_name = None

    uuid = serializers.UUIDField(style={"show": False}, read_only=True)
    name = serializers.CharField(max_length=500, required=True)
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
    project_type = serializers.SerializerMethodField()
    flow_uuid = serializers.SerializerMethodField()
    first_access = serializers.SerializerMethodField()
    wa_demo_token = serializers.SerializerMethodField()
    redirect_url = serializers.SerializerMethodField()

    def get_project_type(self, obj):
        if obj.is_template and obj.template_project.exists():
            return f"template:{obj.template_type}"
        else:
            return "blank"

    def get_flow_uuid(self, obj):
        if obj.is_template and obj.template_project.exists():
            template = obj.template_project.filter(flow_uuid__isnull=False, wa_demo_token__isnull=False, redirect_url__isnull=False).first()
            return template.flow_uuid
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
                template_project = obj.template_project.filter(flow_uuid__isnull=False, wa_demo_token__isnull=False, redirect_url__isnull=False).first()
                template = obj.template_project.create(
                    flow_uuid=template_project.flow_uuid,
                    wa_demo_token=template_project.wa_demo_token,
                    redirect_url=template_project.redirect_url,
                    authorization=authorization
                )
        ...

    def get_wa_demo_token(self, obj):
        if obj.is_template and obj.template_project.exists():
            template = obj.template_project.filter(flow_uuid__isnull=False, wa_demo_token__isnull=False, redirect_url__isnull=False).first()
            return template.wa_demo_token
        ...

    def get_redirect_url(self, obj):
        if obj.is_template and obj.template_project.exists():
            template = obj.template_project.filter(flow_uuid__isnull=False, wa_demo_token__isnull=False, redirect_url__isnull=False).first()
            return template.redirect_url
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
        extra_data = self.context["request"].data.get("project")

        if not extra_data:
            extra_data = {
                "template": self.context["request"].data.get("template"),
                "template_type": self.context["request"].data.get("template_type"),
            }

        is_template = extra_data.get("template")

        created, flows_info = self.create_flows_project(validated_data, user, is_template)

        if not created:
            return flows_info

        instance = Project.objects.create(
            name=validated_data.get("name"),
            flow_id=flows_info.get("id"),
            flow_organization=flows_info.get("uuid"),
            timezone=str(validated_data.get("timezone")),
            organization=validated_data.get("organization"),
            is_template=True if extra_data.get("template") else False,
            created_by=user,
            template_type=extra_data.get("template_type")
        )

        if Project.objects.filter(created_by=user).count() == 1:
            data = dict(
                send_request_flow=settings.SEND_REQUEST_FLOW_PRODUCT,
                flow_uuid=settings.FLOW_PRODUCT_UUID,
                token_authorization=settings.TOKEN_AUTHORIZATION_FLOW_PRODUCT
            )
            user.send_request_flow_user_info(data)

        if is_template:
            extra_data.update(
                {
                    "project": instance.uuid,
                    "authorization": instance.get_user_authorization(user).uuid
                }
            )

            template_serializer = TemplateProjectSerializer(data=extra_data, context=self.context["request"])
            template_serializer.is_valid()
            template_project = template_serializer.save()

            if type(template_project) == dict:
                return template_project

        return instance

    def update(self, instance, validated_data):
        name = validated_data.get("name", instance.name)
        celery_app.send_task(
            "update_project",
            args=[instance.flow_organization, name],
        )
        updated_instance = super().update(instance, validated_data)
        if not settings.TESTING:
            ChatsRESTClient().update_chats_project(instance.uuid)
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

    def create_flows_project(self, data: dict, user: User, is_template: bool):
        flow_instance = FlowsRESTClient()
        created = False
        try:
            if is_template:
                flows_info = flow_instance.create_template_project(
                    data.get("name"),
                    user.email,
                    str(data.get("timezone"))
                )
            else:
                flows_info = flow_instance.create_project(
                    project_name=data.get("name"),
                    user_email=user.email,
                    project_timezone=str(data.get("timezone"))
                )
            created = True
        except Exception as error:
            flows_info = {
                "data": {"message": "Could not create project"},
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR
            }
            logger.error(error)

        return created, flows_info


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

    def validate_project_authorization(self, authorization):
        if authorization.role == 0:
            return False, {
                "message": "Project authorization not setted",
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR
            }
        return True, {}

    def create_globals_omie(self, project: Project, user_email: str):
        from connect.api.v1.internal.flows.mp9.client_omie import Omie

        response_data = {}
        created = False

        omie = Omie()

        data = self.context._data
        globals_dict = data.get("project").get("globals")

        default_globals = {
            "nome_da_empresa": f"{project.name}",
            "nome_do_bot": f"{project.name}",
            "status_boleto_para_desconsiderar": "Recebido, Cancelado",
            "tipo_credenciamento": "email"
        }

        globals_dict.update(default_globals)

        flow_organization = str(project.flow_organization)
        try:
            omie.create_globals(
                flow_organization,
                user_email,
                globals_dict
            )
            created = True
        except Exception as error:
            logger.error(f"Create globals: {error}")
            response_data = {
                "data": {"message": "Could not create global"},
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR
            }
        return created, response_data

    def create(self, validated_data):
        project = validated_data.get("project")
        authorization = validated_data.get("authorization")

        if project.template_type in Project.HAS_GLOBALS:

            created, data = self.create_globals_omie(
                project,
                str(authorization.user.email)
            )

            if not created:
                return data

        is_valid, message = self.validate_project_authorization(authorization)

        if not is_valid:
            # Project delete
            return message

        ok, access_token = project.organization.get_ai_access_token(authorization.user.email, project)
        if not ok:
            # Project delete
            return access_token

        created, classifier_uuid = project.create_classifier(
            authorization,
            project.template_type,
            access_token
        )
        if not created:
            # Project delete
            return classifier_uuid

        created, data = project.create_flows(classifier_uuid)

        if not created:
            # Project delete
            return data

        flow_uuid = data.get("uuid")

        token = self.context._auth

        created, whatsapp_data = project.whatsapp_demo_integration(token)
        if not created:
            return whatsapp_data

        template = project.template_project.create(
            authorization=authorization,
            wa_demo_token=whatsapp_data.get("router_token"),
            redirect_url=whatsapp_data.get("redirect_url"),
            flow_uuid=flow_uuid,
            classifier_uuid=classifier_uuid
        )

        return template
