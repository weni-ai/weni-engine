from rest_framework import serializers

from connect.common.models import Project


class ExternalServiceSerializer(serializers.Serializer):
    project = serializers.SlugRelatedField(
        slug_field="uuid", queryset=Project.objects.all()
    )
