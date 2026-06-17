import json
import uuid
from unittest.mock import patch

from django.test import RequestFactory, TestCase, override_settings
from rest_framework import status
from rest_framework.request import Request
from rest_framework.test import APIClient, force_authenticate

from connect.api.v1.organization.permissions import HasSSOAccess
from connect.api.v1.organization.views import (
    OrganizationAuthorizationViewSet as OrganizationAuthorizationV1ViewSet,
    OrganizationViewSet,
)
from connect.api.v1.project.views import ProjectViewSet as ProjectV1ViewSet
from connect.api.v1.tests.utils import create_user_and_token
from connect.usecases.organizations.sso_access import (
    EvaluateOrganizationSSOAccessUseCase,
)
from connect.api.v2.organizations.views import (
    OrganizationAuthorizationViewSet,
    OrganizationViewSet as OrganizationV2ViewSet,
)
from connect.api.v2.projects.views import ProjectDetailView, ProjectViewSet
from connect.common.mocks import StripeMockGateway
from connect.common.models import (
    BillingPlan,
    Organization,
    OrganizationAuthorization,
    OrganizationRole,
    OrganizationSSOConfig,
    Project,
    ProjectRole,
    ProjectStatus,
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

    def test_enforcing_org_listed_as_disabled_for_non_sso_session(self):
        _, content = self._list_orgs(self.admin_token)
        orgs_by_name = {org["name"]: org for org in content["results"]}
        self.assertIn("Open Org", orgs_by_name)
        self.assertIn("Enforcing Org", orgs_by_name)
        self.assertEqual(orgs_by_name["Open Org"]["access_status"], "active")
        self.assertIsNone(orgs_by_name["Open Org"]["access_disabled_reason"])
        self.assertEqual(orgs_by_name["Enforcing Org"]["access_status"], "disabled")
        self.assertEqual(
            orgs_by_name["Enforcing Org"]["access_disabled_reason"],
            "sso_session_required",
        )

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
        self.assertEqual(orgs_by_name["Enforcing Org"]["access_status"], "active")
        self.assertIsNone(orgs_by_name["Enforcing Org"]["access_disabled_reason"])

    def _retrieve_org(self, organization, token, session_identity_provider=None):
        request = self.factory.get(
            f"/v1/organization/org/{organization.uuid}/",
            HTTP_AUTHORIZATION=f"Token {token.key}",
        )
        request.session_identity_provider = session_identity_provider
        response = OrganizationViewSet.as_view({"get": "retrieve"})(
            request, uuid=str(organization.uuid)
        )
        response.render()
        return response, json.loads(response.content)

    def test_retrieve_returns_disabled_org_for_non_sso_session(self):
        response, content = self._retrieve_org(self.enforcing_org, self.admin_token)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(content["access_status"], "disabled")
        self.assertEqual(content["access_disabled_reason"], "sso_session_required")

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

    @patch(HAS_PASSWORD_CREDENTIAL, return_value=False)
    def test_partial_patch_disabling_blocked_for_non_compliant_session(
        self, _mock_has_password
    ):
        OrganizationSSOConfig.objects.filter(organization=self.enforcing_org).update(
            allowed_sso_providers=["google"],
            allowed_email_domains=["user.com"],
        )
        response = self._sso_settings_request(
            "patch",
            self.enforcing_org,
            self.admin_token,
            data={"is_enabled": False},
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(
            OrganizationSSOConfig.objects.get(
                organization=self.enforcing_org
            ).is_enabled
        )

    @patch(HAS_PASSWORD_CREDENTIAL, return_value=False)
    def test_partial_patch_disabling_preserves_allowlists_for_compliant_session(
        self, _mock_has_password
    ):
        OrganizationSSOConfig.objects.filter(organization=self.enforcing_org).update(
            allowed_sso_providers=["google"],
            allowed_email_domains=["user.com"],
        )
        request = self.factory.patch(
            f"/v1/organization/org/{self.enforcing_org.uuid}/sso-settings/",
            data=json.dumps({"is_enabled": False}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.admin_token.key}",
        )
        request.session_identity_provider = "google"
        response = OrganizationViewSet.as_view({"patch": "update_sso_settings"})(
            request, uuid=str(self.enforcing_org.uuid)
        )
        response.render()
        content = json.loads(response.content)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(content["is_enabled"])
        self.assertEqual(content["allowed_sso_providers"], ["google"])
        self.assertEqual(content["allowed_email_domains"], ["user.com"])


@override_settings(USE_EDA_PERMISSIONS=False)
class SSOEnforcementV2ProjectAccessTestCase(TestCase):
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway):
        mock_get_gateway.return_value = StripeMockGateway()
        self.factory = RequestFactory()
        self.user, self.token = create_user_and_token("sso_v2_project_user")

        self.enforcing_org = Organization.objects.create(
            name="V2 Project Enforcing Org",
            description="V2 Project Enforcing Org",
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

    def test_list_projects_blocked_for_non_compliant_session(self):
        request = self.factory.get(
            f"/v2/organizations/{self.enforcing_org.uuid}/projects/"
        )
        force_authenticate(request, user=self.user, token=self.token)
        request.session_identity_provider = None
        response = ProjectViewSet.as_view({"get": "list"})(
            request, organization_uuid=str(self.enforcing_org.uuid)
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch(
        "connect.internals.event_driven.producer.rabbitmq_publisher.RabbitmqPublisher.send_message"
    )
    def test_create_project_blocked_for_non_compliant_session(self, _mock_publisher):
        request = self.factory.post(
            f"/v2/organizations/{self.enforcing_org.uuid}/projects/",
            data=json.dumps(
                {
                    "date_format": "D",
                    "name": "Blocked Project",
                    "timezone": "America/Argentina/Buenos_Aires",
                }
            ),
            content_type="application/json",
        )
        force_authenticate(request, user=self.user, token=self.token)
        request.session_identity_provider = None
        response = ProjectViewSet.as_view({"post": "create"})(
            request, organization_uuid=str(self.enforcing_org.uuid)
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_set_mode_returns_403_not_404_for_non_compliant_session(self):
        project = Project.objects.create(
            name="Set Mode Project",
            flow_organization=uuid.uuid4(),
            organization=self.enforcing_org,
        )
        request = self.factory.post(
            f"/v2/projects/{project.uuid}/set-mode",
            data=json.dumps({"project_mode": "guided"}),
            content_type="application/json",
        )
        force_authenticate(request, user=self.user, token=self.token)
        request.session_identity_provider = None
        response = ProjectViewSet.as_view({"post": "set_mode"})(
            request, uuid=str(project.uuid)
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_project_detail_blocked_for_non_compliant_session(self):
        project = Project.objects.create(
            name="Detail Blocked Project",
            flow_organization=uuid.uuid4(),
            organization=self.enforcing_org,
        )
        request = self.factory.get(f"/v2/projects/{project.uuid}/detail")
        force_authenticate(request, user=self.user, token=self.token)
        request.session_identity_provider = None
        response = ProjectDetailView.as_view()(request, uuid=str(project.uuid))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


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

    def test_blocks_organization_uuid_kwarg_for_non_compliant_session(self):
        request = self.build_request()
        view = type(
            "View", (), {"kwargs": {"organization_uuid": str(self.enforcing_org.uuid)}}
        )()
        self.assertFalse(self.permission.has_permission(request, view=view))

    def test_blocks_uuid_kwarg_for_non_compliant_session(self):
        request = Request(self.factory.patch("/"))
        request.user = self.user
        request.session_identity_provider = None
        view = type("View", (), {"kwargs": {"uuid": str(self.enforcing_org.uuid)}})()
        self.assertFalse(self.permission.has_permission(request, view=view))

    def test_allows_uuid_kwarg_get_for_organization_read(self):
        request = self.build_request()
        view = type("View", (), {"kwargs": {"uuid": str(self.enforcing_org.uuid)}})()
        self.assertTrue(self.permission.has_permission(request, view=view))

    def test_blocks_uuid_kwarg_get_for_project_non_compliant_session(self):
        project = Project.objects.create(
            name="SSO Read Project",
            flow_organization=uuid.uuid4(),
            organization=self.enforcing_org,
        )
        request = self.build_request()
        view = type("View", (), {"kwargs": {"uuid": str(project.uuid)}})()
        self.assertFalse(self.permission.has_permission(request, view=view))

    def test_blocks_uuid_kwarg_post_for_project_non_compliant_session(self):
        project = Project.objects.create(
            name="SSO Write Project",
            flow_organization=uuid.uuid4(),
            organization=self.enforcing_org,
        )
        request = Request(self.factory.post("/"))
        request.user = self.user
        request.session_identity_provider = None
        view = type("View", (), {"kwargs": {"uuid": str(project.uuid)}})()
        self.assertFalse(self.permission.has_permission(request, view=view))

    @patch(HAS_PASSWORD_CREDENTIAL, return_value=False)
    def test_allows_uuid_kwarg_post_for_project_compliant_session(
        self, _mock_has_password
    ):
        project = Project.objects.create(
            name="SSO Compliant Project",
            flow_organization=uuid.uuid4(),
            organization=self.enforcing_org,
        )
        request = Request(self.factory.post("/"))
        request.user = self.user
        request.session_identity_provider = "google"
        view = type("View", (), {"kwargs": {"uuid": str(project.uuid)}})()
        self.assertTrue(self.permission.has_permission(request, view=view))

    def test_blocks_organization_double_underscore_uuid_kwarg_for_non_compliant_session(
        self,
    ):
        request = Request(self.factory.patch("/"))
        request.user = self.user
        request.session_identity_provider = None
        view = type(
            "View",
            (),
            {"kwargs": {"organization__uuid": str(self.enforcing_org.uuid)}},
        )()
        self.assertFalse(self.permission.has_permission(request, view=view))

    def test_blocks_write_with_organization_in_body_for_non_compliant_session(self):
        request = Request(
            self.factory.post("/", {"organization": str(self.enforcing_org.uuid)})
        )
        request.user = self.user
        request.session_identity_provider = None
        self.assertFalse(self.permission.has_permission(request, view=None))

    def test_allows_organization_read_for_non_compliant_session(self):
        request = self.build_request()
        self.assertTrue(
            self.permission.has_object_permission(
                request, view=None, obj=self.enforcing_org
            )
        )

    def test_blocks_organization_write_for_non_compliant_session(self):
        request = Request(self.factory.patch("/"))
        request.user = self.user
        request.session_identity_provider = None
        self.assertFalse(
            self.permission.has_object_permission(
                request, view=None, obj=self.enforcing_org
            )
        )

    def test_blocks_project_for_non_compliant_session(self):
        project = Project.objects.create(
            name="SSO Project",
            flow_organization=uuid.uuid4(),
            organization=self.enforcing_org,
        )
        request = self.build_request()
        self.assertFalse(
            self.permission.has_object_permission(request, view=None, obj=project)
        )

    def test_blocks_organization_authorization_write_for_non_compliant_session(self):
        authorization = self.enforcing_org.authorizations.get(user=self.user)
        request = Request(self.factory.patch("/"))
        request.user = self.user
        request.session_identity_provider = None
        self.assertFalse(
            self.permission.has_object_permission(request, view=None, obj=authorization)
        )

    def test_allows_organization_authorization_read_for_non_compliant_session(self):
        authorization = self.enforcing_org.authorizations.get(user=self.user)
        request = self.build_request()
        self.assertTrue(
            self.permission.has_object_permission(request, view=None, obj=authorization)
        )

    def test_blocks_enforced_org_read_action_for_non_compliant_session(self):
        request = self.build_request()
        view = type(
            "View",
            (),
            {
                "kwargs": {"uuid": str(self.enforcing_org.uuid)},
                "action": "get_contact_active",
            },
        )()
        self.assertFalse(self.permission.has_permission(request, view=view))
        self.assertFalse(
            self.permission.has_object_permission(
                request, view=view, obj=self.enforcing_org
            )
        )

    def test_blocks_view_with_sso_allow_read_without_compliance_false(self):
        request = self.build_request()
        view = type(
            "View",
            (),
            {
                "kwargs": {"uuid": str(self.enforcing_org.uuid)},
                "action": "retrieve",
                "sso_allow_read_without_compliance": False,
            },
        )()
        self.assertFalse(self.permission.has_permission(request, view=view))
        self.assertFalse(
            self.permission.has_object_permission(
                request, view=view, obj=self.enforcing_org
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

    def test_enforcing_org_listed_as_disabled_for_non_sso_session(self):
        _, content = self._list_orgs()
        orgs_by_name = {org["name"]: org for org in content["results"]}
        self.assertIn("V2 Open Org", orgs_by_name)
        self.assertIn("V2 Enforcing Org", orgs_by_name)
        self.assertEqual(orgs_by_name["V2 Enforcing Org"]["access_status"], "disabled")
        self.assertEqual(
            orgs_by_name["V2 Enforcing Org"]["access_disabled_reason"],
            "sso_session_required",
        )

    @patch(HAS_PASSWORD_CREDENTIAL, return_value=False)
    def test_enforcing_org_listed_for_compliant_session(self, _mock_has_password):
        _, content = self._list_orgs(session_identity_provider="google")
        orgs_by_name = {org["name"]: org for org in content["results"]}
        self.assertIn("V2 Enforcing Org", orgs_by_name)
        self.assertTrue(orgs_by_name["V2 Enforcing Org"]["sso_config"]["is_enabled"])


@override_settings(USE_EDA_PERMISSIONS=False)
class SSOEnforcementAuthorizationViewTestCase(TestCase):
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway):
        mock_get_gateway.return_value = StripeMockGateway()
        self.factory = RequestFactory()
        self.admin, self.admin_token = create_user_and_token("sso_auth_admin")
        self.member, self.member_token = create_user_and_token("sso_auth_member")

        self.enforcing_org = Organization.objects.create(
            name="Auth Enforcing Org",
            description="Auth Enforcing Org",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        self.enforcing_org.authorizations.create(
            user=self.admin, role=OrganizationRole.ADMIN.value
        )
        self.enforcing_org.authorizations.create(
            user=self.member, role=OrganizationRole.CONTRIBUTOR.value
        )
        OrganizationSSOConfig.objects.create(
            organization=self.enforcing_org, is_enabled=True
        )

    def _update_authorization(self, token, session_identity_provider=None):
        request = self.factory.patch(
            f"/v1/organization/authorizations/{self.enforcing_org.uuid}/{self.member.pk}/",
            data=json.dumps({"role": OrganizationRole.ADMIN.value}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {token.key}",
        )
        request.session_identity_provider = session_identity_provider
        return OrganizationAuthorizationV1ViewSet.as_view({"patch": "update"})(
            request,
            organization__uuid=str(self.enforcing_org.uuid),
            user__id=self.member.pk,
        )

    def _destroy_authorization(self, token, session_identity_provider=None):
        request = self.factory.delete(
            f"/v1/organization/authorizations/{self.enforcing_org.uuid}/{self.member.pk}/",
            HTTP_AUTHORIZATION=f"Token {token.key}",
        )
        request.session_identity_provider = session_identity_provider
        return OrganizationAuthorizationV1ViewSet.as_view({"delete": "destroy"})(
            request,
            organization__uuid=str(self.enforcing_org.uuid),
            user__id=self.member.pk,
        )

    @patch(
        "connect.internals.event_driven.producer.rabbitmq_publisher.RabbitmqPublisher.send_message"
    )
    def test_update_authorization_blocked_for_non_compliant_session(
        self, _mock_publisher
    ):
        response = self._update_authorization(self.admin_token)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            self.enforcing_org.get_user_authorization(self.member).role,
            OrganizationRole.CONTRIBUTOR.value,
        )

    @patch(
        "connect.internals.event_driven.producer.rabbitmq_publisher.RabbitmqPublisher.send_message"
    )
    @patch(HAS_PASSWORD_CREDENTIAL, return_value=False)
    def test_update_authorization_succeeds_for_compliant_session(
        self, _mock_has_password, _mock_publisher
    ):
        response = self._update_authorization(
            self.admin_token, session_identity_provider="google"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            self.enforcing_org.get_user_authorization(self.member).role,
            OrganizationRole.ADMIN.value,
        )

    @patch(
        "connect.internals.event_driven.producer.rabbitmq_publisher.RabbitmqPublisher.send_message"
    )
    def test_destroy_authorization_blocked_for_non_compliant_session(
        self, _mock_publisher
    ):
        response = self._destroy_authorization(self.admin_token)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(
            OrganizationAuthorization.objects.filter(
                organization=self.enforcing_org, user=self.member
            ).exists()
        )

    @patch(
        "connect.internals.event_driven.producer.rabbitmq_publisher.RabbitmqPublisher.send_message"
    )
    @patch(HAS_PASSWORD_CREDENTIAL, return_value=False)
    def test_destroy_authorization_succeeds_for_compliant_session(
        self, _mock_has_password, _mock_publisher
    ):
        response = self._destroy_authorization(
            self.admin_token, session_identity_provider="google"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(
            OrganizationAuthorization.objects.filter(
                organization=self.enforcing_org, user=self.member
            ).exists()
        )


@override_settings(USE_EDA_PERMISSIONS=False)
class SSOEnforcementUpdateProjectStatusTestCase(TestCase):
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway):
        mock_get_gateway.return_value = StripeMockGateway()
        self.client = APIClient()
        self.user, self.token = create_user_and_token("sso_update_status_user")

        self.enforcing_org = Organization.objects.create(
            name="Update Status Enforcing Org",
            description="Update Status Enforcing Org",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        self.org_auth = self.enforcing_org.authorizations.create(
            user=self.user, role=OrganizationRole.ADMIN.value
        )
        OrganizationSSOConfig.objects.create(
            organization=self.enforcing_org,
            is_enabled=True,
            allowed_sso_providers=["google"],
            allowed_email_domains=["user.com"],
        )
        self.project = Project.objects.create(
            name="Update Status Project",
            flow_organization=uuid.uuid4(),
            organization=self.enforcing_org,
            status=ProjectStatus.ACTIVE.value,
        )
        project_auth = self.project.project_authorizations.get(user=self.user)
        project_auth.role = ProjectRole.MODERATOR.value
        project_auth.save()
        self.client.force_authenticate(user=self.user)

    def _update_status_url(self):
        return f"/v1/organization/project/{self.project.uuid}/update_status/"

    @patch.object(EvaluateOrganizationSSOAccessUseCase, "execute", return_value=False)
    def test_update_status_blocked_for_non_compliant_session(self, _mock_execute):
        response = self.client.patch(
            self._update_status_url(),
            {"status": ProjectStatus.INACTIVE.value},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.project.refresh_from_db(fields=["status"])
        self.assertEqual(self.project.status, ProjectStatus.ACTIVE.value)

    @patch.object(EvaluateOrganizationSSOAccessUseCase, "execute", return_value=True)
    def test_update_status_succeeds_for_compliant_session(self, _mock_execute):
        response = self.client.patch(
            self._update_status_url(),
            {"status": ProjectStatus.INACTIVE.value},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.project.refresh_from_db(fields=["status"])
        self.assertEqual(self.project.status, ProjectStatus.INACTIVE.value)


@override_settings(
    USE_EDA_PERMISSIONS=False,
    ALLOW_CRM_ACCESS=True,
    CRM_EMAILS_LIST=["crm_sso@user.com"],
)
class SSOEnforcementCRMRetrieveTestCase(TestCase):
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway):
        mock_get_gateway.return_value = StripeMockGateway()
        self.factory = RequestFactory()
        self.crm_user, self.crm_token = create_user_and_token("crm_sso")

        self.enforcing_org = Organization.objects.create(
            name="CRM Retrieve Enforcing Org",
            description="CRM Retrieve Enforcing Org",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        OrganizationSSOConfig.objects.create(
            organization=self.enforcing_org, is_enabled=True
        )

    def test_crm_retrieve_returns_disabled_access_status_for_non_member(self):
        request = self.factory.get(
            f"/v1/organization/org/{self.enforcing_org.uuid}/",
            HTTP_AUTHORIZATION=f"Token {self.crm_token.key}",
        )
        force_authenticate(request, user=self.crm_user, token=self.crm_token)
        request.session_identity_provider = None

        viewset = OrganizationViewSet()
        viewset.action = "retrieve"
        viewset.kwargs = {"uuid": str(self.enforcing_org.uuid)}
        viewset.request = Request(request)
        viewset.format_kwarg = None

        context = viewset.get_serializer_context()
        result = context["sso_access_results"][self.enforcing_org.pk]

        self.assertFalse(result.is_compliant)
        self.assertEqual(result.disabled_reason, "sso_session_required")


@override_settings(USE_EDA_PERMISSIONS=False)
class SSOEnforcementV1ProjectListTestCase(TestCase):
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway):
        mock_get_gateway.return_value = StripeMockGateway()
        self.factory = RequestFactory()
        self.user, self.token = create_user_and_token("sso_v1_list_user")

        self.enforcing_org = Organization.objects.create(
            name="V1 List Enforcing Org",
            description="V1 List Enforcing Org",
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
            name="V1 List Open Org",
            description="V1 List Open Org",
            inteligence_organization=2,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        self.open_org.authorizations.create(
            user=self.user, role=OrganizationRole.ADMIN.value
        )

        self.enforcing_project = self.enforcing_org.project.create(
            name="Enforcing List Project",
            flow_organization=uuid.uuid4(),
        )
        self.open_project = self.open_org.project.create(
            name="Open List Project",
            flow_organization=uuid.uuid4(),
        )
        for project in (self.enforcing_project, self.open_project):
            project_auth = project.project_authorizations.get(user=self.user)
            project_auth.role = ProjectRole.MODERATOR.value
            project_auth.save()

    def _list_projects(self, query_string="", session_identity_provider=None):
        request = self.factory.get(f"/v1/organization/project/{query_string}")
        force_authenticate(request, user=self.user, token=self.token)
        request.session_identity_provider = session_identity_provider
        response = ProjectV1ViewSet.as_view({"get": "list"})(request)
        response.render()
        return response, json.loads(response.content)

    def test_list_excludes_enforcing_org_projects_for_non_compliant_session(self):
        response, content = self._list_projects()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        project_uuids = {project["uuid"] for project in content["results"]}
        self.assertIn(str(self.open_project.uuid), project_uuids)
        self.assertNotIn(str(self.enforcing_project.uuid), project_uuids)

    def test_list_with_enforcing_org_filter_returns_403_for_non_compliant_session(
        self,
    ):
        response, _ = self._list_projects(
            f"?organization={self.enforcing_org.uuid}",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


@override_settings(USE_EDA_PERMISSIONS=False)
class SSOEnforcementV1ProjectSearchTestCase(TestCase):
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway):
        mock_get_gateway.return_value = StripeMockGateway()
        self.factory = RequestFactory()
        self.user, self.token = create_user_and_token("sso_v1_search_user")

        self.enforcing_org = Organization.objects.create(
            name="V1 Search Enforcing Org",
            description="V1 Search Enforcing Org",
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
            name="V1 Search Open Org",
            description="V1 Search Open Org",
            inteligence_organization=2,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        self.open_org.authorizations.create(
            user=self.user, role=OrganizationRole.ADMIN.value
        )

        self.enforcing_project = self.enforcing_org.project.create(
            name="Enforcing Search Project",
            flow_organization=uuid.uuid4(),
        )
        self.open_project = self.open_org.project.create(
            name="Open Search Project",
            flow_organization=uuid.uuid4(),
        )
        for project in (self.enforcing_project, self.open_project):
            project_auth = project.project_authorizations.get(user=self.user)
            project_auth.role = ProjectRole.MODERATOR.value
            project_auth.save()

    @patch("connect.api.v1.project.views.tasks.search_project")
    def test_project_search_blocked_for_cross_org_target(self, _mock_search_project):
        request = self.factory.get(
            f"/v1/organization/project/{self.open_project.uuid}/project-search/",
            {
                "project_uuid": self.enforcing_project.pk,
                "text": "search text",
            },
        )
        force_authenticate(request, user=self.user, token=self.token)
        request.session_identity_provider = None
        response = ProjectV1ViewSet.as_view({"get": "project_search"})(
            request, uuid=str(self.open_project.uuid)
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        _mock_search_project.assert_not_called()


@override_settings(USE_EDA_PERMISSIONS=False)
class SSOEnforcementV2OrganizationAccessTestCase(TestCase):
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway):
        mock_get_gateway.return_value = StripeMockGateway()
        self.factory = RequestFactory()
        self.user, self.token = create_user_and_token("sso_v2_org_access_user")

        self.enforcing_org = Organization.objects.create(
            name="V2 Org Access Enforcing Org",
            description="V2 Org Access Enforcing Org",
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

    def test_list_organization_authorizations_blocked_for_non_compliant_session(
        self,
    ):
        request = self.factory.get(
            f"/v2/organizations/{self.enforcing_org.uuid}/list-organization-authorizations"
        )
        force_authenticate(request, user=self.user, token=self.token)
        request.session_identity_provider = None
        response = OrganizationAuthorizationViewSet.as_view({"get": "retrieve"})(
            request, uuid=str(self.enforcing_org.uuid)
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_contact_active_blocked_for_non_compliant_session(self):
        request = self.factory.get(
            f"/v2/organizations/{self.enforcing_org.uuid}/get_contact_active",
            {"before": "2026-06-30", "after": "2026-06-01"},
        )
        force_authenticate(request, user=self.user, token=self.token)
        request.session_identity_provider = None
        response = OrganizationV2ViewSet.as_view({"get": "get_contact_active"})(
            request, uuid=str(self.enforcing_org.uuid)
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_contacts_active_per_project_blocked_for_non_compliant_session(
        self,
    ):
        request = self.factory.get(
            f"/v1/organization/org/{self.enforcing_org.uuid}/contact-active-per-project/{self.enforcing_org.uuid}/"
        )
        force_authenticate(request, user=self.user, token=self.token)
        request.session_identity_provider = None
        response = OrganizationViewSet.as_view(
            {"get": "get_contacts_active_per_project"}
        )(
            request,
            uuid=str(self.enforcing_org.uuid),
            organization_uuid=str(self.enforcing_org.uuid),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
