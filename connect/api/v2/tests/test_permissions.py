import uuid
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory, force_authenticate
from weni_commons.auth import TOKEN_TYPE_JWT, TOKEN_TYPE_KEYCLOAK, WeniAuthContext

from connect.api.v1.tests.utils import create_user_and_token
from connect.api.v2.permissions import (
    IsProjectContributor,
    IsProjectModerator,
    IsProjectViewer,
    roles_at_least,
)
from connect.common.mocks import StripeMockGateway
from connect.common.models import (
    BillingPlan,
    Organization,
    OrganizationRole,
    Project,
    ProjectAuthorization,
    ProjectRole,
)


VIEWER_ALLOWED = {
    ProjectRole.VIEWER,
    ProjectRole.MARKETING,
    ProjectRole.CONTRIBUTOR,
    ProjectRole.MODERATOR,
    ProjectRole.SUPPORT,
}
CONTRIBUTOR_ALLOWED = {
    ProjectRole.CONTRIBUTOR,
    ProjectRole.MODERATOR,
    ProjectRole.SUPPORT,
}
MODERATOR_ALLOWED = {
    ProjectRole.MODERATOR,
    ProjectRole.SUPPORT,
}


@override_settings(USE_EDA_PERMISSIONS=False)
class ProjectRolePermissionTestCase(TestCase):
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

        self.factory = APIRequestFactory()
        self.user, _ = create_user_and_token("role-user")
        self.organization = Organization.objects.create(
            name="role-org",
            description="role-org",
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        self.org_authorization = self.organization.authorizations.create(
            user=self.user,
            role=OrganizationRole.ADMIN.value,
        )
        self.project = Project.objects.create(
            name="role-project",
            organization=self.organization,
            flow_organization=uuid.uuid4(),
        )
        ProjectAuthorization.objects.filter(user=self.user).delete()

    def _set_role(self, role: ProjectRole) -> None:
        ProjectAuthorization.objects.filter(user=self.user).delete()
        ProjectAuthorization.objects.create(
            user=self.user,
            project=self.project,
            role=role.value,
            organization_authorization=self.org_authorization,
        )

    def _user_request(self, auth: WeniAuthContext = None):
        project_uuid = str(self.project.uuid)
        request = self.factory.get(
            f"/v2/projects/{project_uuid}/detail",
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        auth = auth or WeniAuthContext(
            project_uuid=project_uuid,
            user_email=self.user.email,
            token_type=TOKEN_TYPE_KEYCLOAK,
        )
        force_authenticate(request, user=self.user, token=auth)
        return Request(request)

    def _internal_request(self, user_email: str = None):
        project_uuid = str(self.project.uuid)
        query = {"user_email": user_email} if user_email else None
        request = self.factory.get(f"/v2/projects/{project_uuid}/detail", query)
        auth = WeniAuthContext(
            project_uuid=project_uuid,
            is_internal=True,
            token_type=TOKEN_TYPE_JWT,
        )
        force_authenticate(request, user=self.user, token=auth)
        return Request(request)

    def test_roles_at_least_returns_expected_sets(self):
        self.assertEqual(set(roles_at_least(ProjectRole.VIEWER)), {r.value for r in VIEWER_ALLOWED})
        self.assertEqual(
            set(roles_at_least(ProjectRole.CONTRIBUTOR)),
            {r.value for r in CONTRIBUTOR_ALLOWED},
        )
        self.assertEqual(
            set(roles_at_least(ProjectRole.MODERATOR)),
            {r.value for r in MODERATOR_ALLOWED},
        )

    def test_viewer_tier_allows_expected_roles(self):
        permission = IsProjectViewer()
        for role in ProjectRole:
            with self.subTest(role=role.name):
                self._set_role(role)
                allowed = permission.has_permission(self._user_request(), view=None)
                self.assertEqual(allowed, role in VIEWER_ALLOWED)

    def test_contributor_tier_allows_expected_roles(self):
        permission = IsProjectContributor()
        for role in ProjectRole:
            with self.subTest(role=role.name):
                self._set_role(role)
                allowed = permission.has_permission(self._user_request(), view=None)
                self.assertEqual(allowed, role in CONTRIBUTOR_ALLOWED)

    def test_moderator_tier_allows_expected_roles(self):
        permission = IsProjectModerator()
        for role in ProjectRole:
            with self.subTest(role=role.name):
                self._set_role(role)
                allowed = permission.has_permission(self._user_request(), view=None)
                self.assertEqual(allowed, role in MODERATOR_ALLOWED)

    def test_not_setted_and_chat_user_denied_on_all_tiers(self):
        for role in (ProjectRole.NOT_SETTED, ProjectRole.CHAT_USER):
            self._set_role(role)
            request = self._user_request()
            for permission_cls in (
                IsProjectViewer,
                IsProjectContributor,
                IsProjectModerator,
            ):
                with self.subTest(role=role.name, permission=permission_cls.__name__):
                    self.assertFalse(permission_cls().has_permission(request, view=None))

    def test_internal_without_user_email_is_denied(self):
        self._set_role(ProjectRole.MODERATOR)
        request = self._internal_request(user_email=None)

        self.assertFalse(IsProjectContributor().has_permission(request, view=None))

    def test_internal_with_user_email_is_allowed(self):
        self._set_role(ProjectRole.CONTRIBUTOR)
        request = self._internal_request(user_email=self.user.email)

        self.assertTrue(IsProjectContributor().has_permission(request, view=None))

    def test_missing_auth_context_is_denied(self):
        request = self.factory.get(f"/v2/projects/{self.project.uuid}/detail")
        force_authenticate(request, user=self.user)

        self.assertFalse(IsProjectViewer().has_permission(Request(request), view=None))
