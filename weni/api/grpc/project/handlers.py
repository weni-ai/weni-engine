from weni.api.grpc.project.services import ProjectService
from weni.protos.weni import classifier_pb2_grpc


def grpc_handlers(server):
    classifier_pb2_grpc.add_ProjectClassifierControllerServicer_to_server(
        ProjectService.as_servicer(), server
    )
