import json
import uuid
from datetime import timedelta
from unittest.mock import MagicMock, Mock, patch

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import (
    APIClient,
    APIRequestFactory,
    APITestCase,
    force_authenticate,
)

from connect.api.v1.tests.utils import create_user_and_token
from connect.api.v2.auth.views import (
    GetTokenView,
    InvalidateSessionTokenView,
)
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
from weni_commons.auth import build_cache_key


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
        request = self.factory.get(
            f"/v2/projects/{project_uuid}/get-token",
            data or {"duration": 3600},
        )
        if user is not None:
            force_authenticate(request, user=user, token=user.auth_token)
        return self.view(request, project_uuid=project_uuid)

    @patch(
        "connect.usecases.auth.generate_session_token.DynamoDBSessionTokenRepository"
    )
    @patch("connect.usecases.auth.generate_session_token.get_redis_connection")
    def test_get_token_success(self, mock_get_redis_connection, mock_repo_cls):
        mock_redis = MagicMock()
        mock_get_redis_connection.return_value = mock_redis
        mock_repo = MagicMock()
        mock_repo_cls.return_value = mock_repo

        response = self._request(user=self.user)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("hash", response.data)

        mock_repo.put.assert_called_once()
        put_kwargs = mock_repo.put.call_args.kwargs
        self.assertEqual(put_kwargs["token_hash"], response.data["hash"])
        self.assertEqual(put_kwargs["projeto"], str(self.project.uuid))
        self.assertEqual(put_kwargs["user"], self.user.email)

        mock_redis.setex.assert_called_once()
        redis_key, ttl, payload = mock_redis.setex.call_args[0]
        self.assertEqual(redis_key, build_cache_key(response.data["hash"]))
        self.assertTrue(0 < ttl <= 3600)

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
class InvalidateSessionTokenViewTestCase(TestCase):
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
        self.view = InvalidateSessionTokenView.as_view()

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
        self.other_project = Project.objects.create(
            name="other project",
            flow_organization=uuid.uuid4(),
            organization=self.organization,
        )

    def _payload(self, projeto, user=None, seconds=3600):
        return json.dumps(
            {
                "projeto": str(projeto),
                "user": user or self.user.email,
                "expire_at": (timezone.now() + timedelta(seconds=seconds)).isoformat(),
            }
        ).encode("utf-8")

    def _request(self, token_hash=None, data=None, project_uuid=None):
        project_uuid = project_uuid or str(self.project.uuid)
        headers = {}
        if token_hash is not None:
            headers["HTTP_AUTHORIZATION"] = f"Bearer {token_hash}"

        request = self.factory.post(
            f"/v2/projects/{project_uuid}/invalidate-session-token",
            data if data is not None else {"hash": "target-hash"},
            format="json",
            **headers,
        )
        return self.view(request, project_uuid=project_uuid)

    @patch(
        "connect.usecases.auth.invalidate_session_token.DynamoDBSessionTokenRepository"
    )
    @patch("connect.usecases.auth.invalidate_session_token.get_redis_connection")
    @patch("weni_commons.auth.session.get_redis_connection")
    def test_invalidate_session_token_success(
        self,
        mock_session_get_redis_connection,
        mock_usecase_get_redis_connection,
        mock_repo_cls,
    ):
        mock_redis = MagicMock()
        mock_redis.get.side_effect = lambda key: {
            build_cache_key("session-hash"): self._payload(self.project.uuid),
            build_cache_key("target-hash"): self._payload(self.project.uuid),
        }.get(key)
        mock_session_get_redis_connection.return_value = mock_redis
        mock_usecase_get_redis_connection.return_value = mock_redis
        mock_repo_cls.return_value = MagicMock()

        response = self._request(token_hash="session-hash")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        mock_redis.delete.assert_called_once_with(build_cache_key("target-hash"))
        mock_repo_cls.return_value.delete.assert_called_once_with("target-hash")

    @patch(
        "connect.usecases.auth.invalidate_session_token.DynamoDBSessionTokenRepository"
    )
    @patch("connect.usecases.auth.invalidate_session_token.get_redis_connection")
    @patch("weni_commons.auth.session.get_redis_connection")
    def test_invalidate_session_token_different_project_returns_403(
        self,
        mock_session_get_redis_connection,
        mock_usecase_get_redis_connection,
        mock_repo_cls,
    ):
        mock_redis = MagicMock()
        mock_redis.get.side_effect = lambda key: {
            build_cache_key("session-hash"): self._payload(self.project.uuid),
            build_cache_key("target-hash"): self._payload(self.other_project.uuid),
        }.get(key)
        mock_session_get_redis_connection.return_value = mock_redis
        mock_usecase_get_redis_connection.return_value = mock_redis
        mock_repo_cls.return_value = MagicMock()

        response = self._request(token_hash="session-hash")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        mock_redis.delete.assert_not_called()
        mock_repo_cls.return_value.delete.assert_not_called()

    @patch(
        "connect.usecases.auth.invalidate_session_token.DynamoDBSessionTokenRepository"
    )
    @patch("connect.usecases.auth.invalidate_session_token.get_redis_connection")
    @patch("weni_commons.auth.session.get_redis_connection")
    def test_invalidate_session_token_not_found_returns_404(
        self,
        mock_session_get_redis_connection,
        mock_usecase_get_redis_connection,
        mock_repo_cls,
    ):
        mock_redis = MagicMock()
        mock_redis.get.side_effect = lambda key: {
            build_cache_key("session-hash"): self._payload(self.project.uuid),
        }.get(key)
        mock_session_get_redis_connection.return_value = mock_redis
        mock_usecase_get_redis_connection.return_value = mock_redis
        mock_repo_cls.return_value = MagicMock()
        mock_repo_cls.return_value.get.return_value = None

        response = self._request(token_hash="session-hash")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        mock_redis.delete.assert_not_called()
        mock_repo_cls.return_value.delete.assert_not_called()

    @patch("weni_commons.auth.session.get_redis_connection")
    def test_invalidate_session_token_missing_hash_returns_400(
        self, mock_session_get_redis_connection
    ):
        mock_redis = MagicMock()
        mock_redis.get.return_value = self._payload(self.project.uuid)
        mock_session_get_redis_connection.return_value = mock_redis

        response = self._request(token_hash="session-hash", data={})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalidate_session_token_without_authentication_returns_401(self):
        response = self._request()

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
