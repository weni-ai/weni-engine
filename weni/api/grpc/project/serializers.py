from django_grpc_framework import proto_serializers
from django_grpc_framework.proto_serializers import ProtoSerializer
from rest_framework import serializers

from weni.common.models import Project
from weni.protos.weni import classifier_pb2


class ClassifierRequestSerializer(ProtoSerializer):
    authorization_uuid = serializers.UUIDField()
    # before = serializers.DateTimeField()
    # after = serializers.DateTimeField()

    # def validate(self, data):
    #     if data["after"] > data["before"]:
    #         raise serializers.ValidationError('"after" should be earlier then "before"')
    #     return data

    # def validate_after(self, value):
    #     if value > tz.now():
    #         raise serializers.ValidationError("Cannot search after this date.")
    #     return value

    class Meta:
        proto_class = classifier_pb2.Classifier
