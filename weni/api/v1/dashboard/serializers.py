from rest_framework import serializers

from weni.common.models import Newsletter, ServiceStatus


class NewsletterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Newsletter
        fields = ["id", "title", "description"]
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
            "created_at",
        ]
        ref_name = None

    service__status = serializers.BooleanField(source="service.status")
    service__url = serializers.CharField(source="service.url")
    service__default = serializers.BooleanField(source="service.default")
