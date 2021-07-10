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


class CreateClassifierRequestSerializer(ProtoSerializer):
    classifier_type = serializers.CharField(required=True)
    name = serializers.CharField(required=True)
    access_token = serializers.CharField(required=True)
    user = serializers.CharField(write_only=True)
    project_uuid = serializers.UUIDField(write_only=True)

    class Meta:
        proto_class = project_pb2.ClassifierResponse


class RetrieveClassifierRequestSerializer(ProtoSerializer):
    uuid = serializers.CharField(required=True)

    class Meta:
        proto_class = project_pb2.ClassifierResponse


class DestroyClassifierRequestSerializer(ProtoSerializer):
    uuid = serializers.CharField(required=True)

    class Meta:
        proto_class = project_pb2.ClassifierResponse
