from rest_framework import serializers


class KeycloakAuthSerializer(serializers.Serializer):
    user = serializers.EmailField(required=True)
    password = serializers.CharField(required=True)
