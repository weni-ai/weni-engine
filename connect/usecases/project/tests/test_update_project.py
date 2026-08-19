import uuid
from unittest.mock import patch

from django.test import TestCase

from connect.api.v1.tests.utils import create_user_and_token
from connect.common.mocks import StripeMockGateway
from connect.common.models import (
    BillingPlan,
    Organization,
    OrganizationRole,
    Project,
)
from connect.usecases.project.update_project import UpdateProjectUseCase


class UpdateProjectUseCaseTestCase(TestCase):
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway):
        mock_get_gateway.return_value = StripeMockGateway()
        self.user, _ = create_user_and_token("update_project_uc_user")
        self.organization = Organization.objects.create(
            name="Update Project UC Org",
            description="Update Project UC Org",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        self.organization.authorizations.create(
            user=self.user, role=OrganizationRole.ADMIN.value
        )
        self.project = Project.objects.create(
            name="Update Project UC",
            organization=self.organization,
            created_by=self.user,
            language="pt-br",
            currency="BRL",
            flow_organization=uuid.uuid4(),
        )

    @patch("connect.usecases.project.update_project.ProjectEDAPublisher")
    def test_send_updated_project_includes_currency(self, mock_publisher_cls):
        mock_publisher = mock_publisher_cls.return_value
        UpdateProjectUseCase().send_updated_project(self.project, self.user.email)

        mock_publisher.publish_project_updated.assert_called_once_with(
            project_uuid=self.project.uuid,
            user_email=self.user.email,
            name=self.project.name,
            description=self.project.description,
            language=self.project.language,
            timezone=str(self.project.timezone) if self.project.timezone else None,
            date_format=self.project.date_format,
            config=self.project.config,
            currency="BRL",
        )
