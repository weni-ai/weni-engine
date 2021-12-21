from connect.api.grpc.organization.services import OrganizationService
from weni.protobuf.connect import organization_pb2_grpc


def grpc_handlers(server):
    organization_pb2_grpc.add_OrganizationControllerServicer_to_server(
        OrganizationService.as_servicer(), server
    )
