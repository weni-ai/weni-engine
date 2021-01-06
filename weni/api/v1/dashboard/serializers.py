from rest_framework import serializers

from weni.common.models import Newsletter, ServiceStatus


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
            "created_at",
        ]
        ref_name = None

    service__status = serializers.BooleanField(source="service.status")
    service__url = serializers.CharField(source="service.url")
    service__default = serializers.BooleanField(source="service.default")
    service__last_updated = serializers.DateTimeField(source="service.last_updated")
