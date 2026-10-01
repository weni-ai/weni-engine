from rest_framework import serializers


class KeycloakAuthSerializer(serializers.Serializer):
    user = serializers.EmailField(required=True)
    password = serializers.CharField(required=True)


class InvalidateSessionTokenSerializer(serializers.Serializer):
    hash = serializers.CharField(required=True)


class GetTokenSerializer(serializers.Serializer):
    duration = serializers.IntegerField(required=False, allow_null=True, default=None)
