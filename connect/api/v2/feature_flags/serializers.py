from rest_framework import serializers


class FeatureFlagsRequestSerializer(serializers.Serializer):
    """Serializer for validating feature flags request parameters."""

    project_uuid = serializers.UUIDField(required=True, help_text="UUID of the project")
