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

    def create_organization(self, organization_name: str, user_email: str):
        raise NotImplementedError()

    def delete_organization(self, organization_id: int, user_email: str):
        raise NotImplementedError()

    def update_organization(self, organization_id: int, organization_name: str):
        raise NotImplementedError()

    def update_user_permission_organization(
        self, organization_id: int, user_email: str, permission: int
    ):
        raise NotImplementedError()

    def create_project(
        self,
        project_name: str,
        user_email: str,
        project_timezone: str,
    ):
        raise NotImplementedError()

    def update_project(self, organization_uuid: int, organization_name: str):
        raise NotImplementedError()

    def delete_project(self, project_uuid: int, user_email: str):
        raise NotImplementedError()

    def update_user_permission_project(
        self, organization_uuid: str, user_email: str, permission: int
    ):
        raise NotImplementedError()

    def get_classifiers(self, project_uuid: str, classifier_type: str, is_active: bool):
        raise NotImplementedError()

    def create_classifier(
        self,
        project_uuid: str,
        user_email: str,
        classifier_type: str,
        classifier_name: str,
        access_token: str,
    ):
        raise NotImplementedError()

    def delete_classifier(self, classifier_uuid: str):
        raise NotImplementedError()

    def get_classifier(self, classifier_uuid: str):
        raise NotImplementedError()

    def update_language(self, user_email: str, language: str):
        raise NotImplementedError()

    def get_project_flows(self, project_uuid: str, flow_name: str):
        raise NotImplementedError()

    def get_organization_inteligences(self, inteligence_name: str):
        raise NotImplementedError()

    def get_project_info(self, project_uuid: str):
        raise NotImplementedError()

    def get_project_statistic(self, project_uuid: str):
        raise NotImplementedError()

    def get_organization_statistic(self, organization_id: int):
        raise NotImplementedError()

    def get_count_inteligences_project(self, classifiers: list):
        raise NotImplementedError()

    def get_billing_total_statistics(self, project_uuid: str, before: str, after: str):
        raise NotImplementedError()

    def suspend_or_unsuspend_project(self, project_uuid: str, is_suspended: bool):
        raise NotImplementedError()

    def create_channel(self, name: str, user: str, base_url: str):
        raise NotImplementedError()
