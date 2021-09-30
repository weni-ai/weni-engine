import grpc
from django.conf import settings

from weni.grpc.grpc import GRPCType
from weni.protos.integrations import user_pb2_grpc, user_pb2


class IntegrationsType(GRPCType):
    slug = "integrations"

    def __init__(self):
        self.channel = self.get_channel()

    def get_channel(self):
        if settings.INTEGRATIONS_CERTIFICATE_GRPC_CRT:
            with open(settings.INTEGRATIONS_CERTIFICATE_GRPC_CRT, "rb") as f:
                credentials = grpc.ssl_channel_credentials(f.read())
            return grpc.secure_channel(settings.INTEGRATIONS_GRPC_ENDPOINT, credentials)
        return grpc.insecure_channel(settings.INTEGRATIONS_GRPC_ENDPOINT)

    def update_user_permission_project(
        self, project_uuid: str, user_email: str, permission: int
    ):
        stub = user_pb2_grpc.UserPermissionControllerStub(self.channel)
        response = stub.Update(
            user_pb2.UserPermissionUpdateRequest(
                project_uuid=project_uuid,
                user=user_email,
                role=permission,
            )
        )
        return response
