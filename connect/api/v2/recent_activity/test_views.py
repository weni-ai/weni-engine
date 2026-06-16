import uuid as uuid4
from unittest.mock import Mock, patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from connect.api.v1.tests.utils import create_user_and_token
from connect.authentication.models import User
from connect.common.mocks import StripeMockGateway
from connect.common.models import (
    BillingPlan,
    Organization,
    OrganizationRole,
    Project,
    RecentActivity,
)


class RecentActivityViewSetTestCase(APITestCase):
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
        self.organization.authorizations.create(
            user=self.owner, role=OrganizationRole.ADMIN.value
        )

        self.project = Project.objects.create(
            name="project 1",
            flow_organization=uuid4.uuid4(),
            organization=self.organization,
            contact_count=25,
        )
        self.url = reverse("recent-activities")
        self.recent_activity = RecentActivity.objects.create(
            user=self.owner,
            project=self.project,
            action="ADD",
            entity="USER",
            entity_name=self.project.name,
        )

    @patch("connect.api.v1.internal.permissions.ModuleHasPermission.has_permission")
    def test_create_recent_activity(self, module_has_permission):
        module_has_permission.return_value = True
        activities_before = RecentActivity.objects.count()
        data = {
            "user": self.owner.email,
            "project": str(self.project.uuid),
            "action": "UPDATE",
            "entity": "CAMPAIGN",
        }

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(RecentActivity.objects.count(), activities_before + 1)

        created_activity = RecentActivity.objects.last()
        self.assertEqual(
            created_activity.user, User.objects.get(email=self.owner.email)
        )

    def test_list_recent_activities(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(
            self.url, {"project": str(self.project.uuid)}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)

    def test_list_recent_activities_with_invalid_project(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(
            self.url, {"project": str(uuid4.uuid4())}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["message"], "Project does not exist.")

    def test_list_recent_activities_with_no_permission(self):
        user, _ = create_user_and_token("user")
        self.client.force_authenticate(user=user)

        response = self.client.get(
            self.url, {"project": str(self.project.uuid)}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["message"], "Permission denied.")
