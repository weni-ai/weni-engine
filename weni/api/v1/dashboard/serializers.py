from django.utils import timezone
from django.utils.timezone import timedelta
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers

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
            "project",
            "service__status",
            "service__url",
            "service__default",
            "service__last_updated",
            "service__type_service",
            "created_at",
        ]
        ref_name = None

    service__status = serializers.SerializerMethodField()
    service__url = serializers.CharField(source="service.url")
    service__default = serializers.BooleanField(source="service.default")
    service__last_updated = serializers.SerializerMethodField()
    service__type_service = serializers.ChoiceField(
        choices=Service.SERVICE_TYPE_CHOICES,
        default=Service.SERVICE_TYPE_CHAT,
        label=_("Type Service"),
        source="service.service_type",
        read_only=True,
    )

    def get_service__status(self, obj):
        def percentage(total_requests: int, percentage: int):
            return int(total_requests * (percentage / 100))

        if obj.service.maintenance:
            return "maintenance"

        query = obj.service.log_service.filter(
            created_at__range=[
                timezone.now() - timedelta(minutes=30),
                timezone.now(),
            ],
        )
        total_requests = int(query.count())
        total_fail = int(query.filter(status=False).count())
        total_success = int(query.filter(status=True).count())

        if (
            percentage(total_requests=total_requests, percentage=30) <= total_fail
            and total_success >= 1
        ):
            return "intermittent"
        elif percentage(total_requests=total_requests, percentage=100) <= total_fail:
            return "offline"
        return "online"

    def get_service__last_updated(self, obj):
        return obj.service.log_service.latest("created_at").created_at
