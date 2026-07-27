import datetime
import uuid
from unittest.mock import Mock, patch

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
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

_JWT_PRIVATE_KEY_OBJ = rsa.generate_private_key(public_exponent=65537, key_size=2048)
JWT_PRIVATE_KEY = _JWT_PRIVATE_KEY_OBJ.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
).decode()
JWT_PUBLIC_KEY = (
    _JWT_PRIVATE_KEY_OBJ.public_key()
    .public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    .decode()
)


def build_weni_jwt(**claims) -> str:
    return jwt.encode(claims, JWT_PRIVATE_KEY, algorithm="RS256")


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
        self.assertNotIn("project_uuid", response.data)

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


@override_settings(JWT_PUBLIC_KEY=JWT_PUBLIC_KEY)
class VtexAccountProjectAuthViewTestCase(ProjectAuthorizationViewTestCaseSetUp):
    def _url(self, vtex_account="mystore"):
        return reverse(
            "project-vtex-account-authorizations",
            kwargs={"vtex_account": vtex_account},
        )

    def _get(self, url, token=None, **query):
        headers = {"HTTP_X_WENI_AUTH": token} if token else {}
        return self.client.get(url, query, **headers)

    def test_valid_jwt_returns_role_and_project_uuid(self):
        token = build_weni_jwt(vtex_account="mystore", user_email=self.member.email)
        response = self._get(self._url(), token=token)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user"], self.member.email)
        self.assertEqual(
            response.data["project_authorization"], ProjectRole.CONTRIBUTOR.value
        )
        self.assertEqual(response.data["project_uuid"], str(self.project.uuid))
        self.assertIn("available_roles", response.data)

    def test_jwt_resolves_tenant_from_token_ignoring_path(self):
        token = build_weni_jwt(vtex_account="mystore", user_email=self.member.email)
        response = self._get(self._url(vtex_account="unknown"), token=token)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["project_uuid"], str(self.project.uuid))

    def test_query_param_user_is_ignored_resolving_token_identity(self):
        token = build_weni_jwt(vtex_account="mystore", user_email=self.member.email)
        response = self._get(self._url(), token=token, user=self.internal_user.email)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user"], self.member.email)

    def test_missing_vtex_account_claim_returns_403(self):
        token = build_weni_jwt(project_uuid=str(self.project.uuid))
        response = self._get(self._url(), token=token)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_expired_token_is_rejected_without_fallback(self):
        expired_at = datetime.datetime.utcnow() - datetime.timedelta(minutes=5)
        token = build_weni_jwt(
            vtex_account="mystore",
            user_email=self.member.email,
            exp=expired_at,
        )
        response = self._get(self._url(), token=token)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_missing_token_is_rejected(self):
        response = self._get(self._url())

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_not_found_returns_404(self):
        token = build_weni_jwt(vtex_account="mystore", user_email="ghost@test.user")
        response = self._get(self._url(), token=token)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_project_not_found_returns_404(self):
        token = build_weni_jwt(vtex_account="unknown", user_email=self.member.email)
        response = self._get(self._url(vtex_account="unknown"), token=token)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_multiple_projects_returns_400(self):
        Project.objects.create(
            name="duplicated-project",
            organization=self.organization,
            vtex_account="mystore",
            flow_organization=uuid.uuid4(),
            project_type=TypeProject.COMMERCE,
        )
        token = build_weni_jwt(vtex_account="mystore", user_email=self.member.email)
        response = self._get(self._url(), token=token)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
