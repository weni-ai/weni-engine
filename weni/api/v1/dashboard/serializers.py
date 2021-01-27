from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers

from weni.authentication.models import User
from weni.common.models import Newsletter, ServiceStatus, Service


class NewsletterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Newsletter
        fields = ["id", "title", "description", "created_at"]
        ref_name = None


class StatusServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceStatus
        fields = [
            "id",
            "user",
            "service__status",
            "service__url",
            "service__default",
            "service__last_updated",
            "service__type_service",
            "created_at",
        ]
        ref_name = None

    service__status = serializers.BooleanField(source="service.status")
    service__url = serializers.CharField(source="service.url")
    service__default = serializers.BooleanField(source="service.default")
    service__last_updated = serializers.DateTimeField(source="service.last_updated")
    service__type_service = serializers.ChoiceField(
        choices=Service.TYPE_SERVICE_CHOICES,
        default=Service.TYPE_SERVICE_CHAT,
        label=_("Type Service"),
        source="service.type_service",
        read_only=True,
    )


class DashboardInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["menu"]
        ref_name = None

    menu = serializers.SerializerMethodField()

    def get_menu(self, obj):
        return {
            "inteligence": settings.INTELIGENCE_URL,
            "flows": settings.FLOWS_URL,
            "chat": list(
                obj.service_status.filter(
                    service__type_service=Service.TYPE_SERVICE_CHAT
                ).values_list("service__url", flat=True)
            ),
        }
