from django.conf import settings
from rest_framework import serializers


class KeycloakAuthSerializer(serializers.Serializer):
    user = serializers.EmailField(required=True)
    password = serializers.CharField(required=True)


class GetTokenSerializer(serializers.Serializer):
    duration = serializers.IntegerField(required=True)

    def validate_duration(self, value):
        min_duration = getattr(settings, "SESSION_TOKEN_MIN_DURATION", 60)
        max_duration = getattr(settings, "SESSION_TOKEN_MAX_DURATION", 86400)

        if value < min_duration or value > max_duration:
            raise serializers.ValidationError(
                f"Duration must be between {min_duration} and {max_duration} seconds"
            )
        return value
