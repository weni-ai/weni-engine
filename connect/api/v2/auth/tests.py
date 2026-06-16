import json
import uuid
from unittest.mock import MagicMock, Mock, patch

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APIRequestFactory, APITestCase, force_authenticate

from connect.api.v1.tests.utils import create_user_and_token
from connect.api.v2.auth.views import GetTokenView, ValidateSessionTokenView
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
from connect.usecases.auth.generate_session_token import build_cache_key


@override_settings(USE_EDA_PERMISSIONS=False)
class GetTokenViewTestCase(TestCase):
    @patch(
        "connect.internals.event_driven.producer.rabbitmq_publisher.RabbitmqPublisher.send_message"
    )
    @patch("connect.common.signals.update_user_permission_project")
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway, mock_permission, mock_publisher):
        mock_get_gateway.return_value = StripeMockGateway()
        mock_permission.return_value = True

        self.factory = APIRequestFactory()
        self.user, self.user_token = create_user_and_token("user")
        self.view = GetTokenView.as_view()

        self.organization = Organization.objects.create(
            name="test organization",
            description="",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="free",
        )
        self.org_auth = self.organization.authorizations.create(
            user=self.user, role=OrganizationRole.ADMIN.value
        )
        self.project = Project.objects.create(
            name="test project",
            flow_organization=uuid.uuid4(),
            organization=self.organization,
        )
        ProjectAuthorization.objects.filter(user=self.user).delete()
        ProjectAuthorization.objects.create(
            project=self.project,
            user=self.user,
            role=ProjectRole.MODERATOR.value,
            organization_authorization=self.org_auth,
        )

    def _request(self, data=None, user=None, project_uuid=None):
        project_uuid = project_uuid or str(self.project.uuid)
        request = self.factory.post(
            f"/v2/projects/{project_uuid}/get-token",
            data or {"duration": 3600},
            format="json",
        )
        if user is not None:
            force_authenticate(request, user=user, token=user.auth_token)
        return self.view(request, project_uuid=project_uuid)

    @patch("connect.usecases.auth.generate_session_token.get_redis_connection")
    def test_get_token_success(self, mock_get_redis_connection):
        mock_redis = MagicMock()
        mock_get_redis_connection.return_value = mock_redis

        response = self._request(user=self.user)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("hash", response.data)

        mock_redis.setex.assert_called_once()
        redis_key, ttl, payload = mock_redis.setex.call_args[0]
        self.assertEqual(redis_key, build_cache_key(response.data["hash"]))
        self.assertEqual(ttl, 3600)

        stored_data = json.loads(payload)
        self.assertEqual(stored_data["projeto"], str(self.project.uuid))
        self.assertEqual(stored_data["user"], self.user.email)
        self.assertIn("expire_at", stored_data)

    def test_get_token_without_authentication(self):
        response = self._request()

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_token_without_project_authorization(self):
        other_user, _ = create_user_and_token("other")

        response = self._request(user=other_user)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_token_invalid_duration(self):
        response = self._request(data={"duration": 10}, user=self.user)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


@override_settings(USE_EDA_PERMISSIONS=False)
class ValidateSessionTokenViewTestCase(TestCase):
    @patch(
        "connect.internals.event_driven.producer.rabbitmq_publisher.RabbitmqPublisher.send_message"
    )
    @patch("connect.common.signals.update_user_permission_project")
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway, mock_permission, mock_publisher):
        mock_get_gateway.return_value = StripeMockGateway()
        mock_permission.return_value = True

        self.factory = APIRequestFactory()
        self.user, _ = create_user_and_token("user")
        self.view = ValidateSessionTokenView.as_view()

        self.organization = Organization.objects.create(
            name="test organization",
            description="",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="free",
        )
        self.project = Project.objects.create(
            name="test project",
            flow_organization=uuid.uuid4(),
            organization=self.organization,
        )

    def _request(self, token_hash=None, project_uuid=None):
        project_uuid = project_uuid or str(self.project.uuid)
        headers = {}
        if token_hash is not None:
            headers["HTTP_AUTHORIZATION"] = f"Bearer {token_hash}"

        request = self.factory.get(
            f"/v2/projects/{project_uuid}/validate-session-token",
            **headers,
        )
        return self.view(request, project_uuid=project_uuid)

    @patch("weni_commons.auth.session.get_redis_connection")
    def test_validate_session_token_success(self, mock_get_redis_connection):
        mock_redis = MagicMock()
        payload = {
            "projeto": str(self.project.uuid),
            "user": self.user.email,
            "expire_at": "2026-06-10T12:00:00+00:00",
        }
        mock_redis.get.return_value = json.dumps(payload).encode("utf-8")
        mock_get_redis_connection.return_value = mock_redis

        response = self._request(token_hash="valid-hash")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["projeto"], str(self.project.uuid))
        self.assertEqual(response.data["user"], self.user.email)
        self.assertEqual(response.data["project_uuid"], str(self.project.uuid))

    def test_validate_session_token_without_authorization(self):
        response = self._request()

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("weni_commons.auth.session.get_redis_connection")
    def test_validate_session_token_invalid_hash(self, mock_get_redis_connection):
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        mock_get_redis_connection.return_value = mock_redis

        response = self._request(token_hash="invalid-hash")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


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
