import uuid

from django.test import TestCase
from unittest.mock import patch
from rest_framework.exceptions import NotFound

from connect.api.v1.tests.utils import create_user_and_token
from connect.common.models import (
    Organization,
    BillingPlan,
    OrganizationRole,
    Project,
)
from connect.common.mocks import StripeMockGateway
from connect.usecases.project.get_project_detail import GetProjectDetailUseCase


class GetProjectDetailUseCaseTestCase(TestCase):
    @patch("connect.common.signals.update_user_permission_project")
    @patch("connect.billing.get_gateway")
    @patch(
        "connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.update_user_permission_project"
    )
    @patch(
        "connect.api.v1.internal.integrations.integrations_rest_client.IntegrationsRESTClient.update_user_permission_project"
    )
    def setUp(self, integrations_rest, flows_rest, mock_get_gateway, mock_permission):
        integrations_rest.side_effect = [200, 200]
        flows_rest.side_effect = [200, 200]
        mock_get_gateway.return_value = StripeMockGateway()
        mock_permission.return_value = True

        self.user, _ = create_user_and_token("detail_uc_user")

        self.org = Organization.objects.create(
            name="UC Detail Org",
            description="Org for use case tests",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )

        self.org.authorizations.create(
            user=self.user, role=OrganizationRole.ADMIN.value
        )

        self.project = Project.objects.create(
            name="UC Detail Project",
            flow_organization=uuid.uuid4(),
            organization=self.org,
            config={"nexus_ai_enabled": True},
        )

        self.use_case = GetProjectDetailUseCase()

    def test_execute_returns_project_instance(self):
        result = self.use_case.execute(project_uuid=str(self.project.uuid))

        self.assertIsInstance(result, Project)
        self.assertEqual(result.uuid, self.project.uuid)
        self.assertEqual(result.name, "UC Detail Project")
        self.assertEqual(result.config, {"nexus_ai_enabled": True})

    def test_execute_project_has_billing_relation(self):
        result = self.use_case.execute(project_uuid=str(self.project.uuid))
        billing = result.organization.organization_billing

        self.assertEqual(billing.plan, BillingPlan.PLAN_TRIAL)
        self.assertIsNotNone(billing.trial_end_date)
        self.assertIsNotNone(billing.days_till_trial_end)

    def test_execute_raises_not_found_for_nonexistent_project(self):
        with self.assertRaises(NotFound):
            self.use_case.execute(project_uuid=str(uuid.uuid4()))
