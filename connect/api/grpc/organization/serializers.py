from django_grpc_framework.proto_serializers import ProtoSerializer
from rest_framework import serializers
from google.protobuf import empty_pb2

from connect.common.models import Project
from weni.protobuf.connect import project_pb2
from connect.protos import organization_pb2, organization_pb2_grpc

class OrganizationSerializer(ProtoSerializer):
    uuid = serializers.CharField(required=True)

    class Meta:
        proto_class = organization_pb2.OrganizationResponse