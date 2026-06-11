import json
from unittest.mock import patch

from django.test import RequestFactory, TestCase, override_settings
from rest_framework import status
from rest_framework.request import Request

from connect.api.v1.organization.permissions import HasSSOAccess
from connect.api.v1.organization.views import OrganizationViewSet
from connect.api.v1.tests.utils import create_user_and_token
from connect.api.v2.organizations.views import (
    OrganizationViewSet as OrganizationV2ViewSet,
)
from connect.common.mocks import StripeMockGateway
from connect.common.models import (
    BillingPlan,
    Organization,
    OrganizationRole,
    OrganizationSSOConfig,
)

HAS_PASSWORD_CREDENTIAL = (
    "connect.services.keycloak.service.KeycloakCredentialsService."
    "has_password_credential"
)


@override_settings(USE_EDA_PERMISSIONS=False)
class SSOEnforcementViewTestCase(TestCase):
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway):
        mock_get_gateway.return_value = StripeMockGateway()
        self.factory = RequestFactory()
        self.admin, self.admin_token = create_user_and_token("sso_admin")
        self.viewer, self.viewer_token = create_user_and_token("sso_viewer")

        self.enforcing_org = self._create_org("Enforcing Org")
        self.enforcing_org.authorizations.create(
            user=self.admin, role=OrganizationRole.ADMIN.value
        )
        OrganizationSSOConfig.objects.create(
            organization=self.enforcing_org, is_enabled=True
        )

        self.open_org = self._create_org("Open Org")
        self.open_org.authorizations.create(
            user=self.admin, role=OrganizationRole.ADMIN.value
        )

    def _create_org(self, name):
        return Organization.objects.create(
            name=name,
            description=name,
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )

    def _list_orgs(self, token, session_identity_provider=None):
        request = self.factory.get(
            "/v1/organization/org/",
            HTTP_AUTHORIZATION=f"Token {token.key}",
        )
        request.session_identity_provider = session_identity_provider
        response = OrganizationViewSet.as_view({"get": "list"})(request)
        response.render()
        return response, json.loads(response.content)

    def _sso_settings_request(self, method, organization, token, data=None):
        request = getattr(self.factory, method)(
            f"/v1/organization/org/{organization.uuid}/sso-settings/",
            data=json.dumps(data) if data is not None else None,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {token.key}",
        )
        request.session_identity_provider = None
        view_action = "sso_settings" if method == "get" else "update_sso_settings"
        view = OrganizationViewSet.as_view({method: view_action})
        return view(request, uuid=str(organization.uuid))

    def test_enforcing_org_hidden_for_non_sso_session(self):
        _, content = self._list_orgs(self.admin_token)
        names = [org["name"] for org in content["results"]]
        self.assertIn("Open Org", names)
        self.assertNotIn("Enforcing Org", names)

    def test_sso_settings_get_returns_defaults_for_unconfigured_org(self):
        response = self._sso_settings_request("get", self.open_org, self.admin_token)
        response.render()
        content = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(content["is_enabled"])
        self.assertEqual(content["allowed_email_domains"], [])
        self.assertEqual(content["allowed_sso_providers"], [])

    def test_sso_settings_rejected_for_non_admin(self):
        self.open_org.authorizations.create(
            user=self.viewer, role=OrganizationRole.VIEWER.value
        )
        response = self._sso_settings_request("get", self.open_org, self.viewer_token)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_enabling_sso_locks_out_non_sso_admin(self):
        response = self._sso_settings_request(
            "patch", self.open_org, self.admin_token, data={"is_enabled": True}
        )
        response.render()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(
            OrganizationSSOConfig.objects.filter(
                organization=self.open_org, is_enabled=True
            ).exists()
        )

    def test_enforcing_org_str_includes_organization_name(self):
        config = self.enforcing_org.sso_config
        self.assertEqual(str(config), "SSO config for Enforcing Org")

    @patch(HAS_PASSWORD_CREDENTIAL, return_value=False)
    def test_list_includes_enforcing_org_for_compliant_session(
        self, _mock_has_password
    ):
        _, content = self._list_orgs(
            self.admin_token, session_identity_provider="google"
        )
        orgs_by_name = {org["name"]: org for org in content["results"]}
        self.assertIn("Enforcing Org", orgs_by_name)
        self.assertTrue(orgs_by_name["Enforcing Org"]["sso_config"]["is_enabled"])

    def test_sso_settings_get_returns_existing_config(self):
        response = self._sso_settings_request(
            "get", self.enforcing_org, self.admin_token
        )
        response.render()
        content = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(content["is_enabled"])

    def test_sso_settings_rejected_for_non_member(self):
        response = self._sso_settings_request("get", self.open_org, self.viewer_token)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch(HAS_PASSWORD_CREDENTIAL, return_value=False)
    def test_enabling_sso_succeeds_for_compliant_admin(self, _mock_has_password):
        request = self.factory.patch(
            f"/v1/organization/org/{self.open_org.uuid}/sso-settings/",
            data=json.dumps({"is_enabled": True, "allowed_sso_providers": ["google"]}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.admin_token.key}",
        )
        request.session_identity_provider = "google"
        response = OrganizationViewSet.as_view({"patch": "update_sso_settings"})(
            request, uuid=str(self.open_org.uuid)
        )
        response.render()
        content = json.loads(response.content)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(content["is_enabled"])
        self.assertEqual(content["allowed_sso_providers"], ["google"])


@override_settings(USE_EDA_PERMISSIONS=False)
class HasSSOAccessPermissionTestCase(TestCase):
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway):
        mock_get_gateway.return_value = StripeMockGateway()
        self.factory = RequestFactory()
        self.permission = HasSSOAccess()
        self.user, _ = create_user_and_token("sso_permission_user")

        self.enforcing_org = Organization.objects.create(
            name="Permission Enforcing Org",
            description="Permission Enforcing Org",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        self.enforcing_org.authorizations.create(
            user=self.user, role=OrganizationRole.ADMIN.value
        )
        OrganizationSSOConfig.objects.create(
            organization=self.enforcing_org, is_enabled=True
        )

    def build_request(self, path="/", session_identity_provider=None):
        request = Request(self.factory.get(path))
        request.user = self.user
        request.session_identity_provider = session_identity_provider
        return request

    def test_blocks_organization_query_param_for_non_compliant_session(self):
        request = self.build_request(f"/?organization={self.enforcing_org.uuid}")
        self.assertFalse(self.permission.has_permission(request, view=None))

    def test_allows_request_without_organization_query_param(self):
        request = self.build_request()
        self.assertTrue(self.permission.has_permission(request, view=None))

    def test_blocks_organization_object_for_non_compliant_session(self):
        request = self.build_request()
        self.assertFalse(
            self.permission.has_object_permission(
                request, view=None, obj=self.enforcing_org
            )
        )

    def test_allows_unrelated_objects(self):
        request = self.build_request()
        self.assertTrue(
            self.permission.has_object_permission(request, view=None, obj=object())
        )


@override_settings(USE_EDA_PERMISSIONS=False)
class SSOEnforcementV2ListTestCase(TestCase):
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway):
        mock_get_gateway.return_value = StripeMockGateway()
        self.factory = RequestFactory()
        self.user, self.token = create_user_and_token("sso_v2_user")

        self.enforcing_org = Organization.objects.create(
            name="V2 Enforcing Org",
            description="V2 Enforcing Org",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        self.enforcing_org.authorizations.create(
            user=self.user, role=OrganizationRole.ADMIN.value
        )
        OrganizationSSOConfig.objects.create(
            organization=self.enforcing_org, is_enabled=True
        )

        self.open_org = Organization.objects.create(
            name="V2 Open Org",
            description="V2 Open Org",
            inteligence_organization=2,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        self.open_org.authorizations.create(
            user=self.user, role=OrganizationRole.ADMIN.value
        )

    def _list_orgs(self, session_identity_provider=None):
        request = self.factory.get(
            "/v2/organizations/",
            HTTP_AUTHORIZATION=f"Token {self.token.key}",
        )
        request.session_identity_provider = session_identity_provider
        response = OrganizationV2ViewSet.as_view({"get": "list"})(request)
        response.render()
        return response, json.loads(response.content)

    def test_enforcing_org_hidden_for_non_sso_session(self):
        _, content = self._list_orgs()
        names = [org["name"] for org in content["results"]]
        self.assertIn("V2 Open Org", names)
        self.assertNotIn("V2 Enforcing Org", names)

    @patch(HAS_PASSWORD_CREDENTIAL, return_value=False)
    def test_enforcing_org_listed_for_compliant_session(self, _mock_has_password):
        _, content = self._list_orgs(session_identity_provider="google")
        orgs_by_name = {org["name"]: org for org in content["results"]}
        self.assertIn("V2 Enforcing Org", orgs_by_name)
        self.assertTrue(orgs_by_name["V2 Enforcing Org"]["sso_config"]["is_enabled"])
