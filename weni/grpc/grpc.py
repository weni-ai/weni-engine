import logging
from abc import ABCMeta
from typing import Any

logger = logging.getLogger(__name__)


class GRPCType(metaclass=ABCMeta):
    """
    GRPCAuthType is our abstract base type for custom grpc connection providers. Each provider will
    a way to connect to connect with your service to return information remotely
    """

    def get_channel(self):
        raise NotImplementedError()

    def list_organizations(self, user_email: str):
        raise NotImplementedError()

    def get_user_organization_permission_role(
        self, user_email: str, organization_id: Any
    ):
        raise NotImplementedError()

    def create_organization(
        self, organization_name: str, user_email: str, user_nickname: str
    ):
        raise NotImplementedError()

    def delete_organization(self, organization_id: int, user_email: str):
        raise NotImplementedError()

    def update_organization(self, organization_id: int, organization_name: str):
        raise NotImplementedError()

    def update_user_permission_organization(
        self, organization_id: int, user_email: str, permission: int
    ):
        raise NotImplementedError()
