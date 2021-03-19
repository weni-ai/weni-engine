import grpc

from weni.grpc.grpc import GRPCType
from weni.protos.flow.rapidpro_org import org_pb2_grpc, org_pb2


class FlowType(GRPCType):
    slug = "flow"

    def __init__(self):
        self.channel = self.get_channel()

    def get_channel(self):
        # return grpc.insecure_channel("localhost:50051")
        return grpc.insecure_channel(
            "ac89eabd7753b4776bfc4b0db1c6d9b3-466500662.sa-east-1.elb.amazonaws.com:8002"
        )

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
