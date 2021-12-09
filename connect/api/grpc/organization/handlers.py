from connect.api.grpc.organization.services import OrganizationService
from connect.protos import organization_pb2_grpc


def grpc_handlers(server):
    organization_pb2_grpc.add_OrganizationControllerServicer_to_server(
        OrganizationService.as_servicer(), server
    )
