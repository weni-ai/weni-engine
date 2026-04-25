import json
import uuid

from django.core.cache import cache
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory
from unittest.mock import patch

from connect.api.v1.tests.utils import create_user_and_token
from connect.api.v2.internals.views import InternalProjectPlanStatusView
from connect.common.mocks import StripeMockGateway
from connect.common.models import (
    BillingPlan,
    Organization,
    OrganizationRole,
    Project,
)


class InternalProjectPlanStatusViewTestCase(TestCase):
    @patch("connect.common.signals.update_user_permission_project")
    @patch("connect.billing.get_gateway")
    @patch(
        "connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.update_user_permission_project"
    )
    @patch(
        "connect.api.v1.internal.integrations.integrations_rest_client.IntegrationsRESTClient.update_user_permission_project"
    )
    def setUp(
        self, integrations_rest, flows_rest, mock_get_gateway, mock_permission
    ):
        integrations_rest.side_effect = [200, 200]
        flows_rest.side_effect = [200, 200]
        mock_get_gateway.return_value = StripeMockGateway()
        mock_permission.return_value = True

        self.factory = APIRequestFactory()
        self.user, _ = create_user_and_token("plan_status_view_user")

        self.org = Organization.objects.create(
            name="Plan Status View Org",
            description="Org for plan status view tests",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        self.org.authorizations.create(
            user=self.user, role=OrganizationRole.ADMIN.value
        )
        self.project = Project.objects.create(
            name="Plan Status View Project",
            flow_organization=uuid.uuid4(),
            organization=self.org,
        )
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _request(self, project_uuid):
        path = f"/v2/internals/connect/projects/{project_uuid}/plan-status"
        request = self.factory.get(path)
        view = InternalProjectPlanStatusView.as_view()
        response = view(request, project_uuid=project_uuid)
        response.render()
        return response, json.loads(response.content)

    @patch("connect.api.v1.internal.permissions.ModuleHasPermission.has_permission")
    def test_returns_plan_status_payload(self, module_has_permission):
        module_has_permission.return_value = True

        response, content = self._request(str(self.project.uuid))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(content["plan"], BillingPlan.PLAN_TRIAL)
        self.assertTrue(content["is_trial"])
        self.assertTrue(content["is_trial_active"])
        self.assertTrue(content["is_active"])
        self.assertFalse(content["is_suspended"])
        self.assertEqual(content["project_uuid"], str(self.project.uuid))
        self.assertEqual(content["organization_uuid"], str(self.org.uuid))
        self.assertNotIn("trial_end_date", content)
        self.assertNotIn("days_till_trial_end", content)

    @patch("connect.api.v1.internal.permissions.ModuleHasPermission.has_permission")
    def test_returns_404_for_unknown_project(self, module_has_permission):
        module_has_permission.return_value = True

        response, _ = self._request(str(uuid.uuid4()))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch("connect.api.v1.internal.permissions.ModuleHasPermission.has_permission")
    def test_returns_403_without_internal_permission(self, module_has_permission):
        module_has_permission.return_value = False

        response, _ = self._request(str(self.project.uuid))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
