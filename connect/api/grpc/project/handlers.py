from connect.api.grpc.project.services import ProjectService
from weni.protobuf.connect import project_pb2_grpc


def grpc_handlers(server):
    project_pb2_grpc.add_ProjectControllerServicer_to_server(
        ProjectService.as_servicer(), server
    )
