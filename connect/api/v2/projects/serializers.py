import logging
import json

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
)
from connect.internals.event_driven.producer.rabbitmq_publisher import RabbitmqPublisher
from connect.template_projects.models import TemplateType
from connect.usecases.project.update_project import UpdateProjectUseCase


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
            "authorization",
            "last_opened_on",
            "project_type",
            "flow_uuid",
            "first_access",
            "wa_demo_token",
            "redirect_url",
            "description",
        ]
        ref_name = None

    uuid = serializers.UUIDField(style={"show": False}, read_only=True)
    name = serializers.CharField(max_length=500, required=True)
    description = serializers.CharField(max_length=1000, required=False)
    organization = serializers.PrimaryKeyRelatedField(
        queryset=Organization.objects,
        validators=[CanContributeInOrganizationValidator()],
        required=True,
        style={"show": False},
    )
    timezone = fields.TimezoneField(required=True)
    flow_organization = serializers.UUIDField(style={"show": False}, read_only=True)
    inteligence_count = serializers.IntegerField(read_only=True)
    flow_count = serializers.IntegerField(read_only=True)
    contact_count = serializers.IntegerField(read_only=True)
    total_contact_count = serializers.IntegerField(read_only=True)
    created_at = serializers.DateTimeField(
        required=False, read_only=True, style={"show": False}
    )

    menu = serializers.SerializerMethodField()
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
        extra_data = self.context["request"].data.get("project", {})

        template_uuid = self.context["request"].data.get("uuid")
        is_template = self.context["request"].data.get("template", False)

        if extra_data:
            template_uuid = extra_data.get("uuid", template_uuid)
            is_template = extra_data.get("template", is_template)

        project_template_type = None
        template_name = "blank"
        if is_template:
            project_template_type_queryset = TemplateType.objects.filter(uuid=template_uuid)
            if project_template_type_queryset.exists():
                project_template_type = project_template_type_queryset.first()
                template_name = project_template_type.name

        instance = Project.objects.create(
            name=validated_data.get("name"),
            timezone=str(validated_data.get("timezone")),
            organization=validated_data.get("organization"),
            is_template=is_template,
            created_by=user,
            template_type=template_name,
            project_template_type=project_template_type,
            description=validated_data.get("description", None)
        )

        self.send_request_flow_product(user)
        self.publish_create_project_message(instance)

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

    def publish_create_project_message(self, instance):

        authorizations = []
        for authorization in instance.organization.authorizations.all():
            if authorization.can_contribute:
                authorizations.append({"user_email": authorization.user.email, "role": authorization.role})

        extra_fields = self.context["request"].data.get("globals")
        if extra_fields is None:
            extra_fields = self.context["request"].data.get("project", {}).get("globals", {})

        message_body = {
            "uuid": str(instance.uuid),
            "name": instance.name,
            "is_template": instance.is_template,
            "user_email": instance.created_by.email if instance.created_by else None,
            "date_format": instance.date_format,
            "template_type_uuid": str(instance.project_template_type.uuid) if instance.project_template_type else None,
            "timezone": str(instance.timezone),
            "organization_id": instance.organization.inteligence_organization,
            "extra_fields": extra_fields if instance.is_template else {},
            "authorizations": authorizations,
            "description": instance.description,
            "organization_uuid": str(instance.organization.uuid)
        }
        rabbitmq_publisher = RabbitmqPublisher()
        rabbitmq_publisher.send_message(message_body, exchange="projects.topic", routing_key="")

    def send_request_flow_product(self, user):

        if Project.objects.filter(created_by=user).count() == 1:
            data = dict(
                send_request_flow=settings.SEND_REQUEST_FLOW_PRODUCT,
                flow_uuid=settings.FLOW_PRODUCT_UUID,
                token_authorization=settings.TOKEN_AUTHORIZATION_FLOW_PRODUCT
            )
            celery_app.send_task("send_user_flow_info", args=[data, user.email])

    def update(self, instance, validated_data):
        name = validated_data.get("name", instance.name)
        description = validated_data.get("description", instance.description)
        message_body = {
            "project_uuid": str(instance.uuid),
            "description": description
        }
        rabbitmq_publisher = RabbitmqPublisher()
        rabbitmq_publisher.send_message(message_body, exchange="update-projects.topic", routing_key="")
        celery_app.send_task(
            "update_project",
            args=[instance.uuid, name],
        )
        updated_instance = super().update(instance, validated_data)
        if not settings.TESTING:
            ChatsRESTClient().update_chats_project(instance.uuid)
        return updated_instance

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

    def create_flows_project(self, data: dict, user: User, is_template: bool, project_uuid: str):
        flow_instance = FlowsRESTClient()
        created = False
        try:
            if is_template:
                flows_info = flow_instance.create_template_project(
                    data.get("name"),
                    user.email,
                    str(data.get("timezone")),
                    project_uuid,
                )
                flows_info = json.loads(flows_info.get("data"))
            else:
                flows_info = flow_instance.create_project(
                    project_name=data.get("name"),
                    user_email=user.email,
                    project_timezone=str(data.get("timezone")),
                    project_uuid=project_uuid,
                )
            created = True
        except Exception as error:
            flows_info = {
                "data": {"message": "Could not create project"},
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR
            }
            logger.error(f"Could not create project {error}")

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

    def create_globals_omie(self, project: Project, user_email: str):  # pragma: no cover
        from connect.api.v1.internal.flows.mp9.client_omie import Omie

        response_data = {}
        created = False

        omie = Omie()

        data = self.context._data

        if data.get("project_view"):
            globals_dict = data.get("globals")
        else:
            globals_dict = data.get("project").get("globals")

        if project.template_type in [Project.TYPE_OMIE_PAYMENT_FINANCIAL, Project.TYPE_OMIE_PAYMENT_FINANCIAL_CHAT_GPT]:
            default_globals = {
                "nome_da_empresa": f"{project.name}",
                "nome_do_bot": f"{project.name}",
                "status_boleto_para_desconsiderar": "Recebido, Cancelado",
                "tipo_credenciamento": "email"
            }
        elif project.template_type in [Project.TYPE_OMIE_LEAD_CAPTURE]:
            default_globals = {
                "nome_da_empresa": f"{project.name}",
                "nome_do_bot": f"{project.name}",
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
        template = project.template_project.create(
            authorization=authorization,
            wa_demo_token="wa-demo-12345",
            redirect_url="https://wa.me/5582123456?text=wa-demo-12345",
            flow_uuid=None,
            classifier_uuid=None
        )

        return template

    def _create(self, validated_data):
        project = validated_data.get("project")
        authorization = validated_data.get("authorization")

        data = {}
        if project.template_type in Project.HAS_GLOBALS:

            common_templates = [Project.TYPE_SAC_CHAT_GPT, Project.TYPE_LEAD_CAPTURE_CHAT_GPT]

            if project.template_type in common_templates:
                created, data = self.create_globals(
                    str(project.flow_organization),
                    str(authorization.user.email)
                )
            else:
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
        if not settings.USE_EDA:
            created, data = project.create_flows(classifier_uuid)

            if not created:
                # Project delete
                return data

        flow_uuid = data.get("uuid", str(project.flow_organization))

        template = project.template_project.create(
            authorization=authorization,
            wa_demo_token="wa-demo-12345",
            redirect_url="https://wa.me/5582123456?text=wa-demo-12345",
            flow_uuid=flow_uuid,
            classifier_uuid=classifier_uuid
        )

        return template

    def create_globals(self, project_uuid: str, user_email: str):  # pragma: no cover

        data = self.context._data

        if data.get("project_view"):
            globals_dict = data.get("globals")
        else:
            globals_dict = data.get("project").get("globals")

        flows = FlowsRESTClient()
        body = {
            "org": project_uuid,
            "user": user_email,
        }
        globals_list = []

        for key, value in globals_dict.items():
            payload = {
                "name": key,
                "value": value
            }
            payload.update(body)
            globals_list.append(payload)

        try:
            response = flows.create_globals(globals_list)
            if response.status_code == 201:
                created = True
                return created, response.json()
            raise Exception(response.json())

        except Exception as error:
            logger.error(f"Create globals: {error}")
            response_data = {
                "data": {"message": "Could not create global"},
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR
            }
            created = False
            return created, response_data


class ProjectUpdateSerializer(serializers.ModelSerializer):

    class Meta:
        model = Project
        fields = [
            "name",
            "timezone",
            "date_format",
            "uuid",
            "description"
        ]
        ref_name = None

    name = serializers.CharField(max_length=500, required=False)
    description = serializers.CharField(max_length=1000, required=False)
    timezone = fields.TimezoneField(required=False)
    date_format = serializers.CharField(max_length=1, required=False)

    def update(self, instance, validated_data):  # pragma: no cover
        data = validated_data

        if validated_data.get("timezone"):
            data["timezone"] = str(data["timezone"])

        try:
            instance = super().update(instance, validated_data)
            user = self.context["request"].user
            UpdateProjectUseCase().send_updated_project(instance, user.email)
            return instance
        except Exception as error:
            logger.error(f"Update project: {error}")
            raise error


class ProjectListAuthorizationSerializer(serializers.ModelSerializer):

    class Meta:
        model = Project
        fields = [
            "authorizations",
            "pending_authorizations",
        ]

    authorizations = serializers.SerializerMethodField(style={"show": False})
    pending_authorizations = serializers.SerializerMethodField(style={"show": False})

    def get_authorizations(self, obj):
        authorizations = self.get_existing_authorizations(obj)
        return {
            "count": len(authorizations),
            "users": authorizations,
        }

    def get_existing_authorizations(self, obj):
        exclude_roles = [ProjectRole.SUPPORT.value]
        queryset = obj.project_authorizations.exclude(role__in=exclude_roles).select_related('user')

        return [
            {
                "username": auth.user.username,
                "email": auth.user.email,
                "first_name": auth.user.first_name,
                "last_name": auth.user.last_name,
                "project_role": auth.role,
                "photo_user": auth.user.photo_url,
                "chats_role": self.get_rocketchat_role(auth),
            }
            for auth in queryset
        ]

    def get_rocketchat_role(self, authorization):
        if authorization.rocket_authorization:
            return authorization.rocket_authorization.role
        return None

    def get_pending_authorizations(self, obj):
        pending_authorizations = self.get_pending_authorizations_data(obj)
        return {
            "count": len(pending_authorizations),
            "users": pending_authorizations,
        }

    def get_pending_authorizations_data(self, obj):
        pending_authorizations = obj.requestpermissionproject_set.all()
        return [
            {
                "email": pending.email,
                "project_role": pending.role,
                "created_by": pending.created_by.email,
                "chats_role": self.get_pending_rocketchat_role(pending.email),
            }
            for pending in pending_authorizations
        ]

    def get_pending_rocketchat_role(self, email):
        rocket_authorization = RequestRocketPermission.objects.filter(email=email).first()

        if rocket_authorization:
            return rocket_authorization.role
        return None


class OpenedProjectSerializer(serializers.ModelSerializer):

    class Meta:
        model = OpenedProject
        fields = [
            "day",
            "project",
            "user",
        ]

    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects,
        required=True,
        style={"show": False},
    )
    day = serializers.DateTimeField(required=False)
    project = serializers.SerializerMethodField()

    def get_project(self, obj):
        data = ProjectSerializer(
            obj.project,
            context=self.context
        ).data

        return data
