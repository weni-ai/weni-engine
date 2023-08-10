from django.utils import timezone
from django.utils.timezone import timedelta
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers

from connect.common.models import ServiceStatus, Service, NewsletterLanguage, NewsletterOrganization


class NewsletterSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewsletterLanguage
        fields = ["id", "title", "description", "language", "created_at"]
        ref_name = None


class NewsletterOrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewsletterOrganization
        fields = ["id", "title", "description", "organization", "organization_name", "created_at", "trial_end_date"]
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

    def get_service__status(self, obj):  # pragma: no cover
        def percentage(total_requests: int, percentage: int):
            return int(total_requests * (percentage / 100))

        if obj.service.maintenance:
            return {
                "status": "maintenance",
                "intercurrence": obj.service.start_maintenance,
            }

        query = obj.service.log_service.filter(
            created_at__range=[
                timezone.now() - timedelta(minutes=30),
                timezone.now(),
            ],
        )
        total_requests = int(query.count())
        total_fail = int(query.filter(status=False).count())
        total_success = int(query.filter(status=True).count())

        intercurrence = query.filter(status=False).first()

        if (
            percentage(total_requests=total_requests, percentage=30) <= total_fail
            and total_success >= 1
        ):
            return {
                "status": "intermittent",
                "intercurrence": None
                if intercurrence is None
                else intercurrence.created_at,
            }
        elif percentage(total_requests=total_requests, percentage=100) <= total_fail:
            return {
                "status": "offline",
                "intercurrence": None
                if intercurrence is None
                else intercurrence.created_at,
            }

        intercurrence = obj.service.log_service.filter(
            created_at__range=[
                timezone.now() - timedelta(days=10),
                timezone.now(),
            ],
            status=False,
        ).first()

        return {
            "status": "online",
            "intercurrence": None
            if intercurrence is None
            else intercurrence.created_at,
        }

    def get_service__last_updated(self, obj):  # pragma: no cover
        if obj.service.log_service.all().exists():
            return obj.service.log_service.latest("created_at").created_at
        return None
