from typing import Any

import grpc
from django.conf import settings

from weni.grpc.grpc import GRPCType
from weni.protos.inteligence import (
    organization_pb2_grpc,
    organization_pb2,
    authentication_pb2_grpc,
    authentication_pb2,
    repository_pb2_grpc,
    repository_pb2,
)


class InteligenceType(GRPCType):
    slug = "inteligence"

    def __init__(self):
        self.channel = self.get_channel()

    def get_channel(self):
        if settings.INTELIGENCE_CERTIFICATE_GRPC_CRT:
            with open(settings.INTELIGENCE_CERTIFICATE_GRPC_CRT, "rb") as f:
                credentials = grpc.ssl_channel_credentials(f.read())
            return grpc.secure_channel(settings.INTELIGENCE_GRPC_ENDPOINT, credentials)
        return grpc.insecure_channel(settings.INTELIGENCE_GRPC_ENDPOINT)

    def list_organizations(self, user_email: str):
        result = []
        try:
            stub = organization_pb2_grpc.OrgControllerStub(self.channel)

            for org in stub.List(
                organization_pb2.OrgListRequest(user_email=user_email)
            ):
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
        except grpc.RpcError as e:
            if e.code() is not grpc.StatusCode.NOT_FOUND:
                raise e
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

    def create_organization(self, organization_name: str, user_email: str):
        stub = organization_pb2_grpc.OrgControllerStub(self.channel)
        response = stub.Create(
            organization_pb2.OrgCreateRequest(
                organization_name=organization_name,
                user_email=user_email,
            )
        )
        return response

    def delete_organization(self, organization_id: int, user_email: str):
        stub = organization_pb2_grpc.OrgControllerStub(self.channel)
        stub.Destroy(
            organization_pb2.OrgDestroyRequest(
                id=organization_id, user_email=user_email
            )
        )

    def update_organization(self, organization_id: int, organization_name: str):
        stub = organization_pb2_grpc.OrgControllerStub(self.channel)
        response = stub.Update(
            organization_pb2.OrgUpdateRequest(
                id=organization_id, name=organization_name
            )
        )
        return response

    def update_user_permission_organization(
        self, organization_id: int, user_email: str, permission: int
    ):
        stub = authentication_pb2_grpc.UserPermissionControllerStub(self.channel)
        response = stub.Update(
            authentication_pb2.UserPermissionUpdateRequest(
                org_id=organization_id,
                user_email=user_email,
                permission=permission,
            )
        )
        return response

    def get_organization_inteligences(self, inteligence_name: str):
        result = []
        try:
            stub = repository_pb2_grpc.RepositoryControllerStub(self.channel)
            for inteligence in stub.List(
                repository_pb2.RepositoryListRequest(name=inteligence_name)
            ):
                result.append(
                    {
                        "inteligence_uuid": inteligence.uuid,
                        "inteligence_name": inteligence.name,
                        "inteligence_slug": inteligence.slug,
                        "inteligence_owner": inteligence.owner__nickname,
                    }
                )
        except grpc.RpcError as e:
            if e.code() is not grpc.StatusCode.NOT_FOUND:
                raise e
        return result

    def update_language(self, user_email: str, language: str):
        stub = authentication_pb2_grpc.UserLanguageControllerStub(self.channel)
        response = stub.Update(
            authentication_pb2.UserLanguageUpdateRequest(
                email=user_email, language=language
            )
        )
        return response

    def get_organization_statistic(self, organization_id: int):
        stub = organization_pb2_grpc.OrgControllerStub(self.channel)
        response = stub.Retrieve(
            organization_pb2.OrgStatisticRetrieveRequest(org_id=organization_id)
        )
        return {"repositories_count": response.repositories_count}

    def get_count_inteligences_project(self, classifiers: list):
        stub = repository_pb2_grpc.RepositoryControllerStub(self.channel)

        result = []

        for i in classifiers:
            response = stub.RetrieveAuthorization(
                repository_pb2.RepositoryAuthorizationRetrieveRequest(
                    repository_authorization=i.get("authorization_uuid")
                )
            )
            if response.uuid not in result:
                result.append(i.uuid)

        return {"repositories_count": len(result)}
