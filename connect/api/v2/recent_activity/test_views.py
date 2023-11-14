import uuid as uuid4

from django.urls import reverse
from unittest.mock import patch
from rest_framework import status
from rest_framework.test import APITestCase

from connect.common.models import RecentActivity
from connect.common.models import Project, OrganizationRole, BillingPlan, Organization
from connect.authentication.models import User
from connect.api.v1.tests.utils import create_user_and_token
from connect.api.v2.recent_activity.serializers import RecentActivitySerializer


class RecentActivityViewSetTestCase(APITestCase):
    def setUp(self):
        self.owner, self.owner_token = create_user_and_token("owner")
        self.organization = Organization.objects.create(
            name="test organization",
            description="test organization",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        self.organization_authorization = self.organization.authorizations.create(
            user=self.owner, role=OrganizationRole.ADMIN.value
        )
        self.user, self.user_token = create_user_and_token("user")
        self.project = Project.objects.create(
            name="project 1",
            flow_organization=uuid4.uuid4(),
            organization=self.organization,
            contact_count=25,
        )
        self.url = reverse("recent-activities")
        self.headers = {"Authorization": f"Bearer {self.owner_token}"}
        self.recent_activity = RecentActivity.objects.create(
            user=self.owner,
            project=self.project,
            action=1,
            entity=1,
        )

    @patch("connect.api.v1.internal.permissions.ModuleHasPermission.has_permission")
    def test_create_recent_activity(self, module_has_permission):
        module_has_permission.side_effect = [True, True]
        data = {
            "user": str(self.owner),
            "project": str(self.project.uuid),
            "action": 1,
            "entity": 2,
        }
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # 1 from SetUp, 1 from signal user authentication and 1 from the resquest itself.
        number_of_recent_activities = 3
        self.assertEqual(RecentActivity.objects.count(), number_of_recent_activities)

        created_activity = RecentActivity.objects.last()
        user_activity = User.objects.get(email=self.owner.email)
        self.assertEqual(created_activity.user, user_activity)

    def test_create_recent_activity_with_invalid_project(self):
        data = {
            "project": "invalid-uuid",
            "activity_type": RecentActivity.ActivityType.CREATED.value,
            "message": "Test message",
        }
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(RecentActivity.objects.count(), 0)

    @patch("connect.api.v1.internal.permissions.ModuleHasPermission.has_permission")
    def test_list_recent_activities(self, module_has_permission):

        response = self.client.get(self.url, {"project": str(self.project.uuid)}, format="json", **self.headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0], RecentActivitySerializer(self.recent_activity).data)

    def test_list_recent_activities_with_invalid_project(self):
        response = self.client.get(self.url, {"project": "invalid-uuid"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data["message"], "Project does not exist.")

    def test_list_recent_activities_with_no_permission(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url, {"project": str(self.project.uuid)}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data["message"], "Permission denied.")
