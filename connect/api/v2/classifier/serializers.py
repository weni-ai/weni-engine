from rest_framework import serializers

from connect.common.models import Project

class CreateClassifierSerializer(serializers.Serializer):
    name = serializers.CharField(required=True)
    access_token = serializers.CharField(required=True)
    user = serializers.CharField(write_only=True)
    project_uuid = serializers.UUIDField(write_only=True)


class ListClassifierSerializer(serializers.Serializer):
    project_uuid = serializers.UUIDField(write_only=True)

    def validate_project_uuid(self, value):
        try:
            Project.objects.get(uuid=value)
        except Project.DoesNotExist:
            raise serializers.ValidationError("This project does not exist")
        return value

class RetrieveClassifierSerializer(serializers.Serializer):
    uuid = serializers.CharField(required=True)


class DeleteClassifierSerializer(serializers.Serializer):
    uuid = serializers.CharField(required=True)
    user_email = serializers.CharField(required=True)
