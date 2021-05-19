import grpc
from django.conf import settings

from weni.grpc.grpc import GRPCType
from weni.protos.flow.rapidpro_flow import flow_pb2_grpc, flow_pb2
from weni.protos.flow.rapidpro_org import org_pb2_grpc, org_pb2
from weni.protos.flow.rapidpro_statistic import statistic_pb2_grpc, statistic_pb2
from weni.protos.flow.rapidpro_user import user_pb2_grpc, user_pb2
from weni.protos.flow.rapidpro_classifier import classifier_pb2_grpc, classifier_pb2


class FlowType(GRPCType):
    slug = "flow"

    def __init__(self):
        self.channel = self.get_channel()

    def get_channel(self):
        if settings.FLOW_CERTIFICATE_GRPC_CRT:
            with open(settings.FLOW_CERTIFICATE_GRPC_CRT, "rb") as f:
                credentials = grpc.ssl_channel_credentials(f.read())
            return grpc.secure_channel(settings.FLOW_GRPC_ENDPOINT, credentials)
        return grpc.insecure_channel(settings.FLOW_GRPC_ENDPOINT)

    def create_project(
        self,
        project_name: str,
        user_email: str,
        project_timezone: str,
    ):
        # Create Organization
        stub = org_pb2_grpc.OrgControllerStub(self.channel)
        response = stub.Create(
            org_pb2.OrgCreateRequest(
                name=project_name,
                timezone=project_timezone,
                user_email=user_email,
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

    def get_classifiers(self, project_uuid: str, classifier_type: str):
        result = []
        try:
            stub = classifier_pb2_grpc.ClassifierControllerStub(self.channel)
            for classifier in stub.List(
                classifier_pb2.ClassifierListRequest(
                    org_uuid=project_uuid, classifier_type=classifier_type
                )
            ):
                result.append(
                    {
                        "authorization_uuid": classifier.uuid,
                        "classifier_type": classifier.classifier_type,
                        "name": classifier.name,
                    }
                )
        except grpc.RpcError as e:
            if e.code() is not grpc.StatusCode.NOT_FOUND:
                raise e
        return result

    def update_language(self, user_email: str, language: str):
        stub = user_pb2_grpc.UserControllerStub(self.channel)
        response = stub.Update(
            user_pb2.UpdateUserLang(email=user_email, language=language)
        )
        return response

    def get_project_flows(self, project_uuid: str, flow_name: str):
        result = []
        try:
            stub = flow_pb2_grpc.FlowControllerStub(self.channel)
            for flow in stub.List(
                flow_pb2.FlowListRequest(flow_name=flow_name, org_uuid=project_uuid)
            ):
                result.append(
                    {
                        "flow_uuid": flow.uuid,
                        "flow_name": flow.name,
                    }
                )
        except grpc.RpcError as e:
            if e.code() is not grpc.StatusCode.NOT_FOUND:
                raise e
        return result

    def get_project_info(self, project_uuid: str):
        stub = org_pb2_grpc.OrgControllerStub(self.channel)
        response = stub.Retrieve(org_pb2.OrgRetrieveRequest(uuid=project_uuid))
        return {
            "id": response.id,
            "name": response.name,
            "uuid": response.uuid,
            "timezone": response.timezone,
            "date_format": response.date_format,
        }

    def get_project_statistic(self, project_uuid: str):
        stub = statistic_pb2_grpc.OrgStatisticControllerStub(self.channel)
        response = stub.Retrieve(
            statistic_pb2.OrgStatisticRetrieveRequest(org_uuid=project_uuid)
        )
        return {
            "active_flows": response.active_flows,
            "active_classifiers": response.active_classifiers,
            "active_contacts": response.active_contacts,
        }
