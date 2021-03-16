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
