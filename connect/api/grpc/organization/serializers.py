from django_grpc_framework.proto_serializers import ProtoSerializer
from rest_framework import serializers
from weni.protobuf.connect import organization_pb2


class OrganizationSerializer(ProtoSerializer):
    uuid = serializers.CharField(required=True)

    class Meta:
        proto_class = organization_pb2.OrganizationResponse
