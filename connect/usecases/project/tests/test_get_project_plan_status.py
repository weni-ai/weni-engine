import uuid

from django.core.cache import cache
from django.test import TestCase, override_settings
from unittest.mock import patch
from rest_framework.exceptions import NotFound

from connect.api.v1.tests.utils import create_user_and_token
from connect.common.mocks import StripeMockGateway
from connect.common.models import (
    BillingPlan,
    Organization,
    OrganizationRole,
    Project,
)
from connect.usecases.project.get_project_plan_status import (
    GetProjectPlanStatusUseCase,
    build_cache_key,
    invalidate_organization_plan_status,
    invalidate_project_plan_status,
)


@override_settings(PLAN_STATUS_CACHE_TTL=60)
class GetProjectPlanStatusUseCaseTestCase(TestCase):
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

        self.user, _ = create_user_and_token("plan_status_user")

        self.org = Organization.objects.create(
            name="Plan Status Org",
            description="Org for plan status tests",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        self.org.authorizations.create(
            user=self.user, role=OrganizationRole.ADMIN.value
        )
        self.project = Project.objects.create(
            name="Plan Status Project",
            flow_organization=uuid.uuid4(),
            organization=self.org,
        )

        cache.clear()
        self.use_case = GetProjectPlanStatusUseCase()

    def tearDown(self):
        cache.clear()

    def test_execute_returns_trial_payload(self):
        result = self.use_case.execute(project_uuid=str(self.project.uuid))

        self.assertEqual(result["project_uuid"], str(self.project.uuid))
        self.assertEqual(result["organization_uuid"], str(self.org.uuid))
        self.assertEqual(result["plan"], BillingPlan.PLAN_TRIAL)
        self.assertTrue(result["is_trial"])
        self.assertTrue(result["is_trial_active"])
        self.assertTrue(result["is_active"])
        self.assertFalse(result["is_suspended"])
        self.assertEqual(
            set(result.keys()),
            {
                "project_uuid",
                "organization_uuid",
                "plan",
                "is_trial",
                "is_trial_active",
                "is_active",
                "is_suspended",
            },
        )

    def test_is_trial_active_false_when_org_suspended(self):
        self.org.is_suspended = True
        self.org.save(update_fields=["is_suspended"])

        result = self.use_case.execute(project_uuid=str(self.project.uuid))

        self.assertTrue(result["is_trial"])
        self.assertFalse(result["is_trial_active"])
        self.assertTrue(result["is_suspended"])

    def test_execute_raises_not_found_for_unknown_project(self):
        with self.assertRaises(NotFound):
            self.use_case.execute(project_uuid=str(uuid.uuid4()))

    def test_payload_is_cached_between_calls(self):
        cache_key = build_cache_key(self.project.uuid)
        self.assertIsNone(cache.get(cache_key))

        first = self.use_case.execute(project_uuid=str(self.project.uuid))
        self.assertIsNotNone(cache.get(cache_key))

        with patch.object(
            GetProjectPlanStatusUseCase, "_build_payload"
        ) as build_mock:
            second = self.use_case.execute(project_uuid=str(self.project.uuid))
            build_mock.assert_not_called()

        self.assertEqual(first, second)

    def test_invalidate_project_plan_status_drops_cache(self):
        self.use_case.execute(project_uuid=str(self.project.uuid))
        self.assertIsNotNone(cache.get(build_cache_key(self.project.uuid)))

        invalidate_project_plan_status(self.project.uuid)

        self.assertIsNone(cache.get(build_cache_key(self.project.uuid)))

    def test_invalidate_organization_plan_status_drops_cache(self):
        self.use_case.execute(project_uuid=str(self.project.uuid))
        self.assertIsNotNone(cache.get(build_cache_key(self.project.uuid)))

        invalidate_organization_plan_status(self.org)

        self.assertIsNone(cache.get(build_cache_key(self.project.uuid)))

    def test_billing_change_plan_invalidates_cache(self):
        self.use_case.execute(project_uuid=str(self.project.uuid))
        self.assertIsNotNone(cache.get(build_cache_key(self.project.uuid)))

        self.org.organization_billing.change_plan(BillingPlan.PLAN_START)

        self.assertIsNone(cache.get(build_cache_key(self.project.uuid)))

    def test_org_suspend_invalidates_cache(self):
        self.use_case.execute(project_uuid=str(self.project.uuid))
        self.assertIsNotNone(cache.get(build_cache_key(self.project.uuid)))

        self.org.is_suspended = True
        self.org.save(update_fields=["is_suspended"])

        self.assertIsNone(cache.get(build_cache_key(self.project.uuid)))
