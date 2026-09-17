import uuid as uuid4
from unittest.mock import Mock, patch

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from connect.api.v1.tests.utils import create_user_and_token
from connect.change_history.models import ChangeEvent
from connect.common.mocks import StripeMockGateway
from connect.common.models import (
    BillingPlan,
    Organization,
    OrganizationRole,
    Project,
    ProjectAuthorization,
    ProjectRole,
)


class ProjectChangeHistoryViewSetTestCase(APITestCase):
    @patch("connect.authentication.signals.RabbitmqPublisher")
    @patch("connect.common.signals.RabbitmqPublisher")
    @patch("connect.common.signals.update_user_permission_project")
    @patch("connect.billing.get_gateway")
    def setUp(
        self,
        mock_get_gateway,
        mock_permission,
        mock_rabbitmq_common,
        mock_rabbitmq_auth,
    ):
        mock_get_gateway.return_value = StripeMockGateway()
        mock_permission.return_value = True
        mock_rabbitmq_common.return_value = Mock()
        mock_rabbitmq_auth.return_value = Mock()

        self.owner, self.owner_token = create_user_and_token("owner")
        self.organization = Organization.objects.create(
            name="test organization",
            description="test organization",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        org_auth = self.organization.authorizations.create(
            user=self.owner, role=OrganizationRole.ADMIN.value
        )

        self.project = Project.objects.create(
            name="project 1",
            flow_organization=uuid4.uuid4(),
            organization=self.organization,
            contact_count=25,
        )
        ProjectAuthorization.objects.filter(user=self.owner).delete()
        ProjectAuthorization.objects.create(
            project=self.project,
            user=self.owner,
            role=ProjectRole.MODERATOR.value,
            organization_authorization=org_auth,
        )
        self.url = reverse(
            "change-history", kwargs={"project_uuid": str(self.project.uuid)}
        )
        self.flow_event = self._create_event(
            object_name="Welcome flow",
            module="LIVE_DESK",
            entity="FLOW",
        )
        self.ai_event = self._create_event(
            object_name="Customer Support Assistant",
            module="NEXUS",
            entity="FLOW",
        )

    def _create_event(self, object_name, module, entity):
        return ChangeEvent.objects.create(
            project_uuid=self.project.uuid,
            user_email=self.owner.email,
            occurred_at=timezone.now(),
            action="CREATE",
            entity=entity,
            module=module,
            object_name=object_name,
        )

    def test_list_change_history(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(self.url, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertEqual(len(response.data["results"]), 2)

    def test_list_change_history_filters_by_object_name_search(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(
            self.url, {"object_name": "support"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(
            response.data["results"][0]["object_name"],
            "Customer Support Assistant",
        )

    def test_list_change_history_filters_by_module(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(self.url, {"module": "NEXUS"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["module"], "NEXUS")

    def test_list_change_history_filters_by_entity(self):
        self.client.force_authenticate(user=self.owner)
        self._create_event(
            object_name="Campaign launch",
            module="LIVE_DESK",
            entity="CAMPAIGN",
        )

        response = self.client.get(self.url, {"entity": "CAMPAIGN"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["entity"], "CAMPAIGN")

    def test_list_change_history_filters_by_module_ignoring_case(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(self.url, {"module": "nexus"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["module"], "NEXUS")

    def test_list_change_history_filters_by_entity_ignoring_case(self):
        self.client.force_authenticate(user=self.owner)
        self._create_event(
            object_name="Campaign launch",
            module="LIVE_DESK",
            entity="CAMPAIGN",
        )

        response = self.client.get(self.url, {"entity": "campaign"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["entity"], "CAMPAIGN")

    def test_list_change_history_accepts_page_size(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(self.url, {"page_size": 1}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertIsNotNone(response.data["next"])

    def test_list_change_history_filters_by_module_and_entity(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(
            self.url,
            {"module": "LIVE_DESK", "entity": "FLOW"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["object_name"], "Welcome flow")

    def test_list_change_history_with_no_permission(self):
        user, _ = create_user_and_token("user")
        self.client.force_authenticate(user=user)

        response = self.client.get(self.url, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
