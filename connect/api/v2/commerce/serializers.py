from django.conf import settings
from django.contrib.auth import get_user_model

from rest_framework import serializers
from connect.celery import app as celery_app

from connect.api.v1.fields import TimezoneField
from connect.internals.event_driven.producer.rabbitmq_publisher import RabbitmqPublisher
from connect.usecases.users.create import CreateKeycloakUserUseCase
from connect.usecases.users.user_dto import KeycloakUserDTO

from connect.common.models import (
    BillingPlan,
    Organization,
    OrganizationRole,
    Project,
    TypeProject,
)

User = get_user_model()


class CommerceSerializer(serializers.Serializer):
    user_email = serializers.EmailField(required=True)
    organization_name = serializers.CharField(required=True)
    project_name = serializers.CharField(required=True)
    vtex_account = serializers.CharField(required=True)
    timezone = TimezoneField(required=False, initial="America/Sao_Paulo")

    def publish_create_org_message(self, instance: Organization, user: User):
        authorizations = []
        for authorization in instance.authorizations.all():
            if authorization.can_contribute:
                authorizations.append(
                    {"user_email": authorization.user.email, "role": authorization.role}
                )

        message_body = {
            "uuid": str(instance.uuid),
            "name": instance.name,
            "authorizations": authorizations,
            "user_email": user.email,
        }
        rabbitmq_publisher = RabbitmqPublisher()
        rabbitmq_publisher.send_message(
            message_body, exchange="orgs.topic", routing_key=""
        )

    def send_request_flow_product(self, user):
        if Project.objects.filter(created_by=user).count() == 1:
            data = dict(
                send_request_flow=settings.SEND_REQUEST_FLOW_PRODUCT,
                flow_uuid=settings.FLOW_PRODUCT_UUID,
                token_authorization=settings.TOKEN_AUTHORIZATION_FLOW_PRODUCT,
            )
            celery_app.send_task("send_user_flow_info", args=[data, user.email])

    def publish_create_project_message(self, instance: Project, user: User):
        authorizations = []
        for authorization in instance.organization.authorizations.all():
            if authorization.can_contribute:
                authorizations.append(
                    {"user_email": authorization.user.email, "role": authorization.role}
                )

        message_body = {
            "uuid": str(instance.uuid),
            "name": instance.name,
            "is_template": instance.is_template,
            "user_email": instance.created_by.email if instance.created_by else None,
            "date_format": instance.date_format,
            "template_type_uuid": (
                str(instance.project_template_type.uuid)
                if instance.project_template_type
                else None
            ),
            "timezone": str(instance.timezone),
            "organization_id": instance.organization.inteligence_organization,
            "extra_fields": {},
            "authorizations": authorizations,
            "description": instance.description,
            "organization_uuid": str(instance.organization.uuid),
            "brain_on": True,
            "project_type": instance.project_type.value,
            "vtex_account": instance.vtex_account,
        }
        rabbitmq_publisher = RabbitmqPublisher()
        rabbitmq_publisher.send_message(
            message_body, exchange="projects.topic", routing_key=""
        )

    def create(self, validated_data):
        user_email = validated_data.get("user_email")

        try:
            # Create Keycloak user
            try:
                user_dto = KeycloakUserDTO(email=user_email)
                create_keycloak_user_use_case = CreateKeycloakUserUseCase(user_dto)
                user_info = create_keycloak_user_use_case.execute()
            except Exception as e:
                raise serializers.ValidationError(
                    {"user_email": "User already exists in Keycloak"}
                )

            # Create organization
            organization = Organization.objects.create(
                name=validated_data.get("organization_name"),
                organization_billing__plan="enterprise",
                description=f"Organization {validated_data.get('organization_name')}",
                organization_billing__cycle=BillingPlan._meta.get_field(
                    "cycle"
                ).default,
            )
            organization.authorizations.create(
                user=user_info.get("user"), role=OrganizationRole.ADMIN.value
            )
            self.publish_create_org_message(organization, user_info.get("user"))

            # Create project
            project = Project.objects.create(
                name=validated_data.get("project_name"),
                vtex_account=validated_data.get("vtex_account"),
                timezone=validated_data.get("timezone"),
                organization=organization,
                created_by=user_info.get("user"),
                is_template=False,
                project_type=TypeProject.COMMERCE,
            )
            self.send_request_flow_product(user_info.get("user"))
            self.publish_create_project_message(project, user_info.get("user"))

            # Send email to user
            user = user_info.get("user")
            user.send_email_access_password(user_info.get("password"))

            data = {
                "organization": organization,
                "project": project,
                "user": user_info.get("user"),
            }
        except Exception as e:
            raise serializers.ValidationError({"error": str(e)})
        return data
