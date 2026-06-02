from rest_framework import serializers
from django.contrib.auth import get_user_model

from connect.common.models import Project

User = get_user_model()


class KeycloakAuthSerializer(serializers.Serializer):
    user = serializers.EmailField(required=True)
    password = serializers.CharField(required=True)


class StaffAccessSerializer(serializers.Serializer):
    user = serializers.SlugRelatedField(
        slug_field='email',
        queryset=User.objects.all(),
        required=True
    )

    project = serializers.SlugRelatedField(
        slug_field='uuid',
        queryset=Project.objects.all(),
        required=True
    )
