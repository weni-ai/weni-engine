from typing import Any

import grpc

from weni.grpc.grpc import GRPCType
from weni.protos.inteligence import (
    organization_pb2_grpc,
    organization_pb2,
    authentication_pb2_grpc,
    authentication_pb2,
)


class InteligenceType(GRPCType):
    slug = "inteligence"

    def __init__(self):
        self.channel = self.get_channel()

    def get_channel(self):
        return grpc.insecure_channel("localhost:50051")

    def list_organizations(self, user_email: str):
        stub = organization_pb2_grpc.OrgControllerStub(self.channel)
        result = []
        for org in stub.List(organization_pb2.OrgListRequest(user_email=user_email)):
            result.append(
                {
                    "id": org.id,
                    "name": org.name,
                    "users": {
                        "user_id": org.users[0].org_user_id,
                        "user_email": org.users[0].org_user_email,
                        "user_nickname": org.users[0].org_user_nickname,
                        "user_name": org.users[0].org_user_name,
                    },
                }
            )
        return result

    def get_user_organization_permission_role(
        self, user_email: str, organization_id: Any
    ):
        stub = authentication_pb2_grpc.UserPermissionControllerStub(self.channel)
        response = stub.Retrieve(
            authentication_pb2.UserPermissionRetrieveRequest(
                org_user_email=user_email, org_id=organization_id
            )
        )
        return response.role
