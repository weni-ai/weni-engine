from django.test import TestCase
import uuid
from connect.common.models import (
    Organization,
    BillingPlan,
    Project,
    User,
    RequestPermissionOrganization,
)
from connect.usecases.organization_authorizations.create import CreateOrgAuthUseCase

from connect.usecases.project.exceptions import ProjectDoesNotExist
from connect.usecases.organizations.exceptions import OrganizationDoesNotExist
from connect.usecases.users.exceptions import UserDoesNotExist
from unittest import mock


class MockPublisher:
    def send_message(self, message_body, exchange="orgs-auths.topic", routing_key=""):
        print(message_body)
        pass


class CreateOrgAuthUseCaseTestCase(TestCase):
    def setUp(self):
        self.usecase = CreateOrgAuthUseCase(MockPublisher)
        self.organization = Organization.objects.create(
            name="test organization",
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_ENTERPRISE,
        )
        self.project = Project.objects.create(
            name="Project",
            organization=self.organization,
        )
        self.user = User.objects.create(
            email="user@does.exists",
            username="user@does.exists"
        )
        self.crm = User.objects.create(
            email="crm@email.com",
            username="crm@email.com"
        )

        self.not_org = str(uuid.uuid4())
        self.not_project = str(uuid.uuid4())
        self.not_user = "userdoes@not.exist"

    def test_user_does_not_exist(self):
        msg_body = {
            "user": self.not_user,
            "org_uuid": self.not_org,
            "project_uuid": self.not_project,
        }
        with self.assertRaises(UserDoesNotExist):
            self.usecase.create_organization_authorization(msg_body)

    def test_org_does_not_exist(self):
        msg_body = {
            "user": self.user.email,
            "org_uuid": self.not_org,
            "project_uuid": self.not_project,
        }
        with self.assertRaises(OrganizationDoesNotExist):
            self.usecase.create_organization_authorization(msg_body)

    @mock.patch("connect.common.models.OrganizationAuthorization.publish_create_org_authorization_message")
    def test_create_request_permission_organization(self, publisher):
        RequestPermissionOrganization.objects.create(
            email=self.user,
            organization=self.organization,
            role=3,
            created_by=self.crm,
        )
