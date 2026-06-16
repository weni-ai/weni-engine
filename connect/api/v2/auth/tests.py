import json
import uuid
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from connect.api.v1.tests.utils import create_user_and_token
from connect.api.v2.auth.views import GetTokenView, ValidateSessionTokenView
from connect.common.mocks import StripeMockGateway
from connect.common.models import (
    BillingPlan,
    Organization,
    OrganizationRole,
    Project,
    ProjectAuthorization,
    ProjectRole,
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
