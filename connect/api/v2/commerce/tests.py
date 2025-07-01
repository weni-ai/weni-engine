import uuid
from unittest.mock import patch, Mock
from django.test import override_settings
from django.urls import reverse
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from connect.api.v1.tests.utils import create_user_and_token
from connect.authentication.models import User
from connect.common.models import (
    Organization,
    OrganizationAuthorization,
    Project,
    ProjectAuthorization,
    ProjectRole,
    OrganizationRole,
    BillingPlan,
    TypeProject,
)
from connect.common.mocks import StripeMockGateway


@override_settings(USE_EDA_PERMISSIONS=False)  # Disable EDA to avoid RabbitMQ issues
class CommerceProjectCheckExistsTestCase(APITestCase):
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

        self.client = APIClient()
        self.user, self.token = create_user_and_token("testuser")

        # Add permission for internal communication
        content_type = ContentType.objects.get_for_model(User)
        permission, created = Permission.objects.get_or_create(
            codename="can_communicate_internally",
            name="can communicate internally",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        # Authenticate the client
        self.client.force_authenticate(user=self.user)

        # Create organization using the manager method
        self.organization = Organization.objects.create(
            name="Test Organization",
            description="Test organization for commerce tests",
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )

        # Create project
        self.project = Project.objects.create(
            name="Test Commerce Project",
            organization=self.organization,
            vtex_account="test-vtex-account",
            flow_organization=uuid.uuid4(),
            project_type=TypeProject.COMMERCE,
        )

        # Create organization authorization first
        self.org_authorization = OrganizationAuthorization.objects.create(
            user=self.user,
            organization=self.organization,
            role=OrganizationRole.ADMIN.value,
        )

        # Create project authorization
        ProjectAuthorization.objects.create(
            user=self.user,
            project=self.project,
            role=ProjectRole.CONTRIBUTOR.value,
            organization_authorization=self.org_authorization,
        )

        # Create another user for tests
        self.other_user, _ = create_user_and_token("otheruser")

        self.url = reverse("check-exists-project")

    def test_project_exists_user_has_permission(self):
        """Test when project exists and user has permission"""
        response = self.client.get(
            self.url,
            {"user_email": self.user.email, "vtex_account": "test-vtex-account"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["has_project"], True)
        self.assertEqual(
            str(response.data["data"]["project_uuid"]), str(self.project.uuid)
        )
        self.assertIn("exists and user", response.data["message"])

    @patch("connect.api.v2.commerce.views.capture_exception")
    def test_project_does_not_exist_sentry_called(self, mock_capture_exception):
        """Test when project doesn't exist - should call Sentry"""
        response = self.client.get(
            self.url,
            {
                "user_email": self.user.email,
                "vtex_account": "non-existent-vtex-account",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["has_project"], False)
        self.assertIn("doesn't exists", response.data["message"])

        # Verify Sentry was called
        mock_capture_exception.assert_called_once()

        # Verify the exception is Project.DoesNotExist
        call_args = mock_capture_exception.call_args[0]
        self.assertIsInstance(call_args[0], Project.DoesNotExist)

    def test_missing_vtex_account_parameter(self):
        """Test when vtex_account parameter is missing"""
        response = self.client.get(self.url, {"user_email": self.user.email})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["has_project"], False)

    @patch("connect.api.v2.commerce.views.capture_exception")
    def test_project_not_found_vtex_account(self, mock_capture_exception):
        """Test searching for project with non-existent vtex_account"""
        response = self.client.get(
            self.url,
            {
                "user_email": self.user.email,
                "vtex_account": "totally-non-existent-vtex-account",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["has_project"], False)
        self.assertIn("doesn't exists", response.data["message"])

        # Verify Sentry was called for the DoesNotExist exception
        mock_capture_exception.assert_called_once()
        call_args = mock_capture_exception.call_args[0]
        self.assertIsInstance(call_args[0], Project.DoesNotExist)
