from rest_framework import serializers


class FeatureFlagsRequestSerializer(serializers.Serializer):
    """Serializer for validating feature flags request parameters."""
    
    project_uuid = serializers.UUIDField(required=True, help_text="UUID of the project")


class FeatureFlagSerializer(serializers.Serializer):
    """Serializer for a single feature flag."""
    
    key = serializers.CharField()
    value = serializers.JSONField()
    
    class Meta:
        fields = ["key", "value"]


class FeatureFlagsResponseSerializer(serializers.Serializer):
    """Serializer for feature flags response."""
    
    features = FeatureFlagSerializer(many=True)
    
    class Meta:
        fields = ["features"]



