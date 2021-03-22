import grpc
from django.conf import settings

from weni.grpc.grpc import GRPCType
from weni.protos.flow.rapidpro_org import org_pb2_grpc, org_pb2
from weni.protos.flow.rapidpro_user import user_pb2_grpc, user_pb2


class FlowType(GRPCType):
    slug = "flow"

    def __init__(self):
        self.channel = self.get_channel()

    def get_channel(self):
        return grpc.insecure_channel(settings.FLOW_GRPC_ENDPOINT)

    def create_project(
        self,
        project_name: str,
        user_email: str,
        user_username: str,
        project_timezone: str,
    ):
        # Create Organization
        stub = org_pb2_grpc.OrgControllerStub(self.channel)
        response = stub.Create(
            org_pb2.OrgCreateRequest(
                name=project_name,
                timezone=project_timezone,
                user_email=user_email,
                username=user_username,
            )
        )
        return response

    def update_project(
        self, organization_uuid: int, user_email: str, organization_name: str
    ):
        stub = org_pb2_grpc.OrgControllerStub(self.channel)
        response = stub.Update(
            org_pb2.OrgUpdateRequest(
                uuid=organization_uuid, user_email=user_email, name=organization_name
            )
        )
        return response

    def delete_project(self, project_uuid: int, user_email: str):
        stub = org_pb2_grpc.OrgControllerStub(self.channel)
        stub.Destroy(
            org_pb2.OrgDestroyRequest(uuid=project_uuid, user_email=user_email)
        )

    def update_user_permission_project(
        self, organization_uuid: str, user_email: str, permission: int
    ):
        permissions = {1: "viewer", 2: "editor", 3: "administrator"}

        stub = user_pb2_grpc.UserPermissionControllerStub(self.channel)
        response = stub.Update(
            user_pb2.UserPermissionUpdateRequest(
                org_uuid=organization_uuid,
                user_email=user_email,
                permission=permissions.get(permission),
            )
        )
        return response
