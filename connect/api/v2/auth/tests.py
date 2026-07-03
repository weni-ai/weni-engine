import uuid
from unittest.mock import Mock, patch

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from connect.api.v1.tests.utils import create_user_and_token
from connect.authentication.models import User
from connect.common.mocks import StripeMockGateway
from connect.common.models import (
    BillingPlan,
    Organization,
    OrganizationRole,
    Project,
    ProjectAuthorization,
    ProjectRole,
    TypeProject,
)


@override_settings(USE_EDA_PERMISSIONS=False)
class ProjectAuthorizationViewTestCaseSetUp(APITestCase):
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

        self.member, _ = create_user_and_token("member")
        self.internal_user, _ = create_user_and_token("internal")
        self.regular_user, _ = create_user_and_token("regular")

        content_type = ContentType.objects.get_for_model(User)
        permission, _ = Permission.objects.get_or_create(
            codename="can_communicate_internally",
            name="can communicate internally",
            content_type=content_type,
        )
        self.internal_user.user_permissions.add(permission)

        self.organization = Organization.objects.create(
            name="auth-org",
            description="auth-org",
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        self.project = Project.objects.create(
            name="auth-project",
            organization=self.organization,
            vtex_account="mystore",
            flow_organization=uuid.uuid4(),
            project_type=TypeProject.COMMERCE,
        )
        self.org_authorization = self.organization.authorizations.create(
            user=self.member,
            role=OrganizationRole.CONTRIBUTOR.value,
        )
        self.authorization = ProjectAuthorization.objects.create(
            user=self.member,
            project=self.project,
            role=ProjectRole.CONTRIBUTOR.value,
            organization_authorization=self.org_authorization,
        )
        self.client = APIClient()


class ProjectAuthViewTestCase(ProjectAuthorizationViewTestCaseSetUp):
    def _url(self, project_uuid=None):
        return reverse(
            "project-authorizations",
            kwargs={"project_uuid": project_uuid or str(self.project.uuid)},
        )

    def test_self_lookup_returns_role(self):
        self.client.force_authenticate(user=self.member)
        response = self.client.get(self._url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user"], self.member.email)
        self.assertEqual(
            response.data["project_authorization"], ProjectRole.CONTRIBUTOR.value
        )
        self.assertIn("available_roles", response.data)

    def test_other_user_lookup_with_internal_permission_returns_role(self):
        self.client.force_authenticate(user=self.internal_user)
        response = self.client.get(self._url(), {"user": self.member.email})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user"], self.member.email)

    def test_other_user_lookup_without_permission_returns_403(self):
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(self._url(), {"user": self.member.email})

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_authorization_not_found_returns_404(self):
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(self._url())

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class VtexAccountProjectAuthViewTestCase(ProjectAuthorizationViewTestCaseSetUp):
    def _url(self, vtex_account="mystore"):
        return reverse(
            "project-vtex-account-authorizations",
            kwargs={"vtex_account": vtex_account},
        )

    def test_self_lookup_returns_role(self):
        self.client.force_authenticate(user=self.member)
        response = self.client.get(self._url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user"], self.member.email)
        self.assertEqual(
            response.data["project_authorization"], ProjectRole.CONTRIBUTOR.value
        )
        self.assertIn("available_roles", response.data)

    def test_other_user_lookup_with_internal_permission_returns_role(self):
        self.client.force_authenticate(user=self.internal_user)
        response = self.client.get(self._url(), {"user": self.member.email})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user"], self.member.email)

    def test_other_user_lookup_without_permission_returns_403(self):
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(self._url(), {"user": self.member.email})

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_not_found_returns_404(self):
        self.client.force_authenticate(user=self.internal_user)
        response = self.client.get(self._url(), {"user": "ghost@test.user"})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_project_not_found_returns_404(self):
        self.client.force_authenticate(user=self.member)
        response = self.client.get(self._url(vtex_account="unknown"))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_multiple_projects_returns_400(self):
        Project.objects.create(
            name="duplicated-project",
            organization=self.organization,
            vtex_account="mystore",
            flow_organization=uuid.uuid4(),
            project_type=TypeProject.COMMERCE,
        )
        self.client.force_authenticate(user=self.internal_user)
        response = self.client.get(self._url(), {"user": self.member.email})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
