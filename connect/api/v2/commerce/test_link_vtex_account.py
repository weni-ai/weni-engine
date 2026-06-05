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
    BillingPlan,
    Organization,
    Project,
    TypeProject,
)
from connect.common.mocks import StripeMockGateway
from connect.usecases.commerce.exceptions import (
    ProjectAlreadyHasVtexAccountError,
    VtexAccountAlreadyLinkedError,
)
from connect.usecases.commerce.link_vtex_account import LinkVtexAccountUseCase


@override_settings(USE_EDA_PERMISSIONS=False)
class LinkVtexAccountViewTestCase(APITestCase):
    """Tests for POST /v2/commerce/projects/<uuid>/link-vtex-account/"""

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
        self.user, self.token = create_user_and_token("linkuser")

        content_type = ContentType.objects.get_for_model(User)
        permission, _ = Permission.objects.get_or_create(
            codename="can_communicate_internally",
            name="can communicate internally",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)
        self.client.force_authenticate(user=self.user)

        self.organization = Organization.objects.create(
            name="link-org",
            description="Organization link-org",
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        self.project = Project.objects.create(
            name="link-project",
            organization=self.organization,
            flow_organization=uuid.uuid4(),
            project_type=TypeProject.COMMERCE,
        )

    def _url(self, project_uuid=None):
        uid = project_uuid or str(self.project.uuid)
        return reverse("link-vtex-account", kwargs={"project_uuid": uid})

    @patch("connect.usecases.commerce.link_vtex_account.InsightsRESTClient")
    def test_link_vtex_account_successfully(self, mock_insights):
        response = self.client.post(
            self._url(),
            {"vtex_account": "mystore"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"success": True})

        self.project.refresh_from_db()
        self.assertEqual(self.project.vtex_account, "mystore")

    @patch("connect.usecases.commerce.link_vtex_account.InsightsRESTClient")
    def test_project_already_has_vtex_account_returns_400(self, mock_insights):
        self.project.vtex_account = "existing"
        self.project.save(update_fields=["vtex_account"])

        response = self.client.post(
            self._url(),
            {"vtex_account": "mystore"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("connect.usecases.commerce.link_vtex_account.InsightsRESTClient")
    def test_vtex_account_already_linked_returns_400(self, mock_insights):
        Project.objects.create(
            name="other-project",
            organization=self.organization,
            vtex_account="mystore",
            flow_organization=uuid.uuid4(),
            project_type=TypeProject.COMMERCE,
        )

        response = self.client.post(
            self._url(),
            {"vtex_account": "mystore"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_project_not_found_returns_404(self):
        response = self.client.post(
            self._url(str(uuid.uuid4())),
            {"vtex_account": "mystore"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_missing_vtex_account_returns_400(self):
        response = self.client.post(self._url(), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_request_returns_403(self):
        unauth_client = APIClient()
        other_user, _ = create_user_and_token("noperm-link")
        unauth_client.force_authenticate(user=other_user)

        response = unauth_client.post(
            self._url(),
            {"vtex_account": "mystore"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


@override_settings(USE_EDA_PERMISSIONS=False)
class LinkVtexAccountUseCaseTestCase(APITestCase):
    """Unit tests for LinkVtexAccountUseCase."""

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

        self.organization = Organization.objects.create(
            name="uc-link-org",
            description="Organization uc-link-org",
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        self.project = Project.objects.create(
            name="uc-link-project",
            organization=self.organization,
            flow_organization=uuid.uuid4(),
            project_type=TypeProject.COMMERCE,
        )
        self.insights = Mock()

    def _use_case(self):
        return LinkVtexAccountUseCase(insights_client=self.insights)

    def test_execute_links_and_notifies_insights(self):
        result = self._use_case().execute(str(self.project.uuid), "mystore")

        self.assertEqual(result, {"success": True})
        self.project.refresh_from_db()
        self.assertEqual(self.project.vtex_account, "mystore")

        self.insights.notify_vtex_account_migration.assert_called_once_with(
            project_uuid=str(self.project.uuid),
            vtex_account="mystore",
        )

    def test_execute_raises_when_project_already_linked(self):
        self.project.vtex_account = "existing"
        self.project.save(update_fields=["vtex_account"])

        with self.assertRaises(ProjectAlreadyHasVtexAccountError):
            self._use_case().execute(str(self.project.uuid), "mystore")

        self.insights.notify_vtex_account_migration.assert_not_called()

    def test_execute_raises_when_account_used_by_another_project(self):
        Project.objects.create(
            name="other",
            organization=self.organization,
            vtex_account="mystore",
            flow_organization=uuid.uuid4(),
            project_type=TypeProject.COMMERCE,
        )

        with self.assertRaises(VtexAccountAlreadyLinkedError):
            self._use_case().execute(str(self.project.uuid), "mystore")

    def test_execute_raises_when_project_not_found(self):
        with self.assertRaises(Project.DoesNotExist):
            self._use_case().execute(str(uuid.uuid4()), "mystore")

    def test_insights_notification_failure_does_not_break_link(self):
        self.insights.notify_vtex_account_migration.side_effect = Exception(
            "insights down"
        )

        result = self._use_case().execute(str(self.project.uuid), "mystore")

        self.assertEqual(result, {"success": True})
        self.project.refresh_from_db()
        self.assertEqual(self.project.vtex_account, "mystore")
