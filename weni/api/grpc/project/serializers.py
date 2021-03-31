from django_grpc_framework.proto_serializers import ProtoSerializer
from rest_framework import serializers

from weni.common.models import Project
from weni.protos.weni import project_pb2


class ClassifierRequestSerializer(ProtoSerializer):
    project_uuid = serializers.UUIDField()

    def validate_project_uuid(self, value):
        try:
            Project.objects.get(uuid=value)
        except Project.DoesNotExist:
            raise serializers.ValidationError("This project does not exist")
        return value

    class Meta:
        proto_class = project_pb2.ClassifierResponse
