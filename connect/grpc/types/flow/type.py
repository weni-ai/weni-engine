import grpc
from django.conf import settings

from connect.grpc.grpc import GRPCType
from weni.protobuf.flows import billing_pb2_grpc, billing_pb2
from weni.protobuf.flows import channel_pb2_grpc, channel_pb2
from weni.protobuf.flows import flow_pb2_grpc, flow_pb2
from weni.protobuf.flows import org_pb2_grpc, org_pb2
from weni.protobuf.flows import statistic_pb2_grpc, statistic_pb2
from weni.protobuf.flows import user_pb2_grpc, user_pb2
from weni.protobuf.flows import classifier_pb2_grpc, classifier_pb2


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

    def get_classifiers(self, project_uuid: str, classifier_type: str, is_active: bool):
        result = []
        try:
            stub = classifier_pb2_grpc.ClassifierControllerStub(self.channel)
            for classifier in stub.List(
                classifier_pb2.ClassifierListRequest(
                    org_uuid=project_uuid,
                    classifier_type=classifier_type,
                    is_active=is_active,
                )
            ):
                result.append(
                    {
                        "authorization_uuid": classifier.access_token,
                        "classifier_type": classifier.classifier_type,
                        "name": classifier.name,
                        "is_active": classifier.is_active,
                        "uuid": classifier.uuid,
                    }
                )
        except grpc.RpcError as e:
            if e.code() is not grpc.StatusCode.NOT_FOUND:
                raise e
        return result

    def create_classifier(
        self,
        project_uuid: str,
        user_email: str,
        classifier_type: str,
        classifier_name: str,
        access_token: str,
    ):
        # Create Classifier
        stub = classifier_pb2_grpc.ClassifierControllerStub(self.channel)
        response = stub.Create(
            classifier_pb2.ClassifierCreateRequest(
                org=project_uuid,
                user=user_email,
                classifier_type=classifier_type,
                name=classifier_name,
                access_token=access_token,
            )
        )
        return {
            "uuid": response.uuid,
            "classifier_type": response.classifier_type,
            "name": response.name,
            "access_token": response.access_token,
            "is_active": response.is_active,
        }

    def delete_classifier(self, classifier_uuid: str):
        stub = classifier_pb2_grpc.ClassifierControllerStub(self.channel)
        stub.Destroy(classifier_pb2.ClassifierDestroyRequest(uuid=classifier_uuid))

    def get_classifier(self, classifier_uuid: str):
        stub = classifier_pb2_grpc.ClassifierControllerStub(self.channel)
        response = stub.Retrieve(
            classifier_pb2.ClassifierRetrieveRequest(uuid=classifier_uuid)
        )
        return {
            "uuid": response.uuid,
            "classifier_type": response.classifier_type,
            "name": response.name,
            "access_token": response.access_token,
            "is_active": response.is_active,
        }

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

    def get_billing_total_statistics(self, project_uuid: str, before: str, after: str):
        stub = billing_pb2_grpc.BillingStub(self.channel)
        response = stub.Total(
            billing_pb2.BillingRequest(
                org_uuid=project_uuid, before=before, after=after
            )
        )
        return {"active_contacts": response.active_contacts}

    def suspend_or_unsuspend_project(self, project_uuid: str, is_suspended: bool):
        stub = org_pb2_grpc.OrgControllerStub(self.channel)
        response = stub.Update(
            org_pb2.OrgUpdateRequest(
                uuid=project_uuid,
                is_suspended=is_suspended,
            )
        )
        return response

    def create_channel(self, user: str, project_uuid: str, data: str, channeltype_code: str):
        # Create Channel
        stub = channel_pb2_grpc.ChannelControllerStub(self.channel)
        response = stub.Create(
            channel_pb2.ChannelCreateRequest(
                user=user,
                org=project_uuid,
                data=data,
                channeltype_code=channeltype_code,
            )
        )
        return response

    def release_channel(self, channel_uuid: str, user: str):
        stub = channel_pb2_grpc.ChannelControllerStub(self.channel)
        response = stub.Destroy(
            channel_pb2.ChannelDestroyRequest(
                user=user,
                uuid=channel_uuid,
            )
        )
        return response
