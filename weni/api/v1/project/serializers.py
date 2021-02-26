import uuid as uuid4

from django.conf import settings
from rest_framework import serializers

from weni.api.v1.project.validators import CanContributeInOrganizationValidator
from weni.common.models import Service, Project, Organization


class ProjectSeralizer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = [
            "uuid",
            "name",
            "organization",
            "timezone",
            "date_format",
            "flow_organization",
            "flow_organization_id",
            "menu",
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
    timezone = serializers.CharField(read_only=True)
    menu = serializers.SerializerMethodField()
    flow_organization = serializers.UUIDField(
        style={"show": False},
        read_only=True,
        source="organization.flow_organization",
    )
    flow_organization_id = serializers.IntegerField(read_only=True)

    def get_menu(self, obj):
        return {
            "inteligence": settings.INTELIGENCE_URL,
            "flows": settings.FLOWS_URL,
            "chat": list(
                obj.service_status.filter(
                    service__service_type=Service.SERVICE_TYPE_CHAT
                ).values_list("service__url", flat=True)
            ),
        }

    def create(self, validated_data):
        import random

        validated_data.update({"flow_organization": uuid4.uuid4()})
        validated_data.update({"flow_organization_id": random.randint(0, 1000000)})
        return super().create(validated_data)
