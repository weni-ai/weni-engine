import json
from typing import Optional
from unittest.mock import patch

from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings
from rest_framework import status

from connect.api.v1.organization.views import OrganizationViewSet
from connect.api.v1.tests.utils import create_user_and_token
from connect.common.mocks import StripeMockGateway
from connect.common.models import (
    BillingPlan,
    Organization,
    OrganizationRole,
    OrganizationSSOConfig,
)
from connect.usecases.organizations.exceptions import (
    SSOConfigLockoutError,
    SSOPolicyValidationError,
)
from connect.usecases.organizations.tests.test_sso_access import FakeCredentialsService
from connect.usecases.organizations.update_sso_config import (
    UpdateOrganizationSSOConfigDTO,
    UpdateOrganizationSSOConfigUseCase,
)

LOC_MEM_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "sso-update-config-tests",
    }
}


def _use_case_with_fake_credentials(*_args, **_kwargs):
    return UpdateOrganizationSSOConfigUseCase(
        credentials_service=FakeCredentialsService(has_password=False)
    )


HAS_PASSWORD_CREDENTIAL = (
    "connect.services.keycloak.service.KeycloakCredentialsService."
    "has_password_credential"
)


@override_settings(
    USE_EDA_PERMISSIONS=False,
    CACHES=LOC_MEM_CACHE,
    SSO_INTERNAL_BYPASS_EMAIL_DOMAINS=["weni.ai", "vtex.com"],
)
class UpdateOrganizationSSOConfigUseCaseTestCase(TestCase):
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway):
        mock_get_gateway.return_value = StripeMockGateway()
        cache.clear()
        self.actor, _ = create_user_and_token("sso_update_actor")
        self.organization = Organization.objects.create(
            name="SSO Update Org",
            description="SSO Update Org",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        self.organization.authorizations.create(
            user=self.actor, role=OrganizationRole.ADMIN.value
        )
        self.provider = "google"

    def execute(
        self, dto, session_identity_provider, has_password: Optional[bool] = False
    ):
        usecase = UpdateOrganizationSSOConfigUseCase(
            credentials_service=FakeCredentialsService(has_password=has_password)
        )
        return usecase.execute(
            organization=self.organization,
            dto=dto,
            actor=self.actor,
            session_identity_provider=session_identity_provider,
        )

    def test_creates_config_when_enabling(self):
        dto = UpdateOrganizationSSOConfigDTO(
            is_enabled=True,
            allowed_email_domains=["user.com"],
            allowed_sso_providers=["google"],
        )
        config = self.execute(dto, self.provider)

        self.assertTrue(config.is_enabled)
        self.assertEqual(config.allowed_email_domains, ["user.com"])
        self.assertEqual(config.allowed_sso_providers, ["google"])
        self.assertTrue(
            OrganizationSSOConfig.objects.filter(
                organization=self.organization, is_enabled=True
            ).exists()
        )

    def test_updates_existing_config(self):
        OrganizationSSOConfig.objects.create(
            organization=self.organization, is_enabled=False
        )
        dto = UpdateOrganizationSSOConfigDTO(
            is_enabled=True, allowed_sso_providers=["google"]
        )
        config = self.execute(dto, self.provider)

        self.assertTrue(config.is_enabled)
        self.assertEqual(
            OrganizationSSOConfig.objects.filter(
                organization=self.organization
            ).count(),
            1,
        )

    def test_disabling_does_not_require_actor_compliance(self):
        dto = UpdateOrganizationSSOConfigDTO(is_enabled=False)
        config = self.execute(dto, None, has_password=True)
        self.assertFalse(config.is_enabled)

    def test_enabling_raises_lockout_for_non_sso_session(self):
        dto = UpdateOrganizationSSOConfigDTO(is_enabled=True)
        with self.assertRaises(SSOConfigLockoutError):
            self.execute(dto, None)

    def test_enabling_raises_lockout_for_disallowed_provider(self):
        dto = UpdateOrganizationSSOConfigDTO(
            is_enabled=True, allowed_sso_providers=["microsoft"]
        )
        with self.assertRaises(SSOConfigLockoutError):
            self.execute(dto, "google")

    def test_enabling_raises_lockout_for_disallowed_email_domain(self):
        dto = UpdateOrganizationSSOConfigDTO(
            is_enabled=True, allowed_email_domains=["weni.ai"]
        )
        with self.assertRaises(SSOConfigLockoutError):
            self.execute(dto, "google")

    def test_enabling_allows_internal_bypass_domain_actor(self):
        self.actor.email = "staff@weni.ai"
        self.actor.save(update_fields=["email"])
        dto = UpdateOrganizationSSOConfigDTO(
            is_enabled=True,
            allowed_email_domains=["customer.com"],
            allowed_sso_providers=["microsoft"],
        )
        config = self.execute(dto, None, has_password=True)

        self.assertTrue(config.is_enabled)
        self.assertEqual(config.allowed_email_domains, ["customer.com"])
        self.assertEqual(config.allowed_sso_providers, ["microsoft"])

    def test_enabling_raises_lockout_when_actor_has_password(self):
        dto = UpdateOrganizationSSOConfigDTO(is_enabled=True)
        with self.assertRaises(SSOConfigLockoutError):
            self.execute(dto, "google", has_password=True)

    def test_enabling_raises_lockout_when_credential_unavailable(self):
        dto = UpdateOrganizationSSOConfigDTO(is_enabled=True)
        with self.assertRaises(SSOConfigLockoutError):
            self.execute(dto, "google", has_password=None)

    def test_partial_disable_preserves_existing_allowlists(self):
        OrganizationSSOConfig.objects.create(
            organization=self.organization,
            is_enabled=True,
            allowed_sso_providers=["google"],
            allowed_email_domains=["example.com"],
        )
        dto = UpdateOrganizationSSOConfigDTO(is_enabled=False)
        config = self.execute(dto, None, has_password=True)

        self.assertFalse(config.is_enabled)
        self.assertEqual(config.allowed_sso_providers, ["google"])
        self.assertEqual(config.allowed_email_domains, ["example.com"])

    def test_lockout_does_not_persist_config_changes(self):
        dto = UpdateOrganizationSSOConfigDTO(is_enabled=True)
        with self.assertRaises(SSOConfigLockoutError):
            self.execute(dto, None)

        self.assertFalse(
            OrganizationSSOConfig.objects.filter(
                organization=self.organization, is_enabled=True
            ).exists()
        )

    def _config_snapshot(self, config):
        config.refresh_from_db()
        return (
            config.is_enabled,
            list(config.allowed_email_domains),
            list(config.allowed_sso_providers),
            config.requires_customer_identity_source,
        )

    def _create_marked_complete_config(self):
        return OrganizationSSOConfig.objects.create(
            organization=self.organization,
            is_enabled=True,
            allowed_email_domains=["user.com"],
            allowed_sso_providers=["google"],
            requires_customer_identity_source=True,
        )

    def test_emptying_a_list_on_marked_org_is_rejected_and_row_is_unchanged(self):
        config = self._create_marked_complete_config()
        snapshot = self._config_snapshot(config)
        cases = (
            UpdateOrganizationSSOConfigDTO(allowed_sso_providers=[]),
            UpdateOrganizationSSOConfigDTO(allowed_email_domains=[]),
        )
        for dto in cases:
            with self.subTest(dto=dto):
                with self.assertRaises(SSOPolicyValidationError):
                    self.execute(dto, self.provider)
                self.assertEqual(self._config_snapshot(config), snapshot)

    def test_validation_runs_before_lockout_guard(self):
        self._create_marked_complete_config()
        dto = UpdateOrganizationSSOConfigDTO(
            allowed_sso_providers=["microsoft"],
            allowed_email_domains=[],
        )
        try:
            self.execute(dto, self.provider)
        except SSOConfigLockoutError:
            self.fail(
                "incomplete resulting state must raise SSOPolicyValidationError, "
                "not SSOConfigLockoutError"
            )
        except SSOPolicyValidationError as exc:
            self.assertNotIn(
                "Your current SSO provider is not in the allowed providers",
                str(exc),
            )
        else:
            self.fail("expected SSOPolicyValidationError")

    def test_marked_org_accepts_valid_non_empty_domain_list_edit(self):
        config = self._create_marked_complete_config()
        dto = UpdateOrganizationSSOConfigDTO(
            allowed_email_domains=["user.com", "partner.com"]
        )

        result = self.execute(dto, self.provider)
        config.refresh_from_db()

        self.assertEqual(result.allowed_email_domains, ["user.com", "partner.com"])
        self.assertEqual(config.allowed_email_domains, ["user.com", "partner.com"])
        self.assertTrue(config.is_enabled)
        self.assertEqual(config.allowed_sso_providers, ["google"])
        self.assertTrue(config.requires_customer_identity_source)

    def test_marked_org_rejects_disabling_enforcement_and_row_is_unchanged(self):
        config = self._create_marked_complete_config()
        snapshot = self._config_snapshot(config)
        dto = UpdateOrganizationSSOConfigDTO(is_enabled=False)

        with self.assertRaises(SSOPolicyValidationError):
            self.execute(dto, self.provider)

        self.assertEqual(self._config_snapshot(config), snapshot)


@override_settings(
    USE_EDA_PERMISSIONS=False,
    CACHES=LOC_MEM_CACHE,
    SSO_INTERNAL_BYPASS_EMAIL_DOMAINS=["weni.ai", "vtex.com"],
)
class UpdateOrganizationSSOConfigAdminPathViewTestCase(TestCase):
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway):
        mock_get_gateway.return_value = StripeMockGateway()
        cache.clear()
        self.factory = RequestFactory()
        self.admin, self.admin_token = create_user_and_token("sso_update_admin")
        self.organization = Organization.objects.create(
            name="SSO Admin Path Org",
            description="SSO Admin Path Org",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        self.organization.authorizations.create(
            user=self.admin, role=OrganizationRole.ADMIN.value
        )
        self.config = OrganizationSSOConfig.objects.create(
            organization=self.organization,
            is_enabled=True,
            allowed_email_domains=["user.com"],
            allowed_sso_providers=["google"],
            requires_customer_identity_source=True,
        )

    def _config_snapshot(self):
        self.config.refresh_from_db()
        return (
            self.config.is_enabled,
            list(self.config.allowed_email_domains),
            list(self.config.allowed_sso_providers),
            self.config.requires_customer_identity_source,
        )

    def _patch_sso_settings(self, data, session_identity_provider="google"):
        request = self.factory.patch(
            f"/v1/organization/org/{self.organization.uuid}/sso-settings/",
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.admin_token.key}",
        )
        request.session_identity_provider = session_identity_provider
        return OrganizationViewSet.as_view({"patch": "update_sso_settings"})(
            request, uuid=str(self.organization.uuid)
        )

    @patch(HAS_PASSWORD_CREDENTIAL, return_value=False)
    @patch(
        "connect.api.v1.organization.views.UpdateOrganizationSSOConfigUseCase",
        _use_case_with_fake_credentials,
    )
    def test_patch_ignores_requires_customer_identity_source_and_keeps_stored_marker(
        self, _mock_has_password
    ):
        snapshot = self._config_snapshot()
        response = self._patch_sso_settings(
            {"requires_customer_identity_source": False}
        )
        response.render()
        content = json.loads(response.content)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("requires_customer_identity_source", content)
        self.assertEqual(self._config_snapshot(), snapshot)
        self.assertTrue(self.config.requires_customer_identity_source)

    @patch(HAS_PASSWORD_CREDENTIAL, return_value=False)
    @patch(
        "connect.api.v1.organization.views.UpdateOrganizationSSOConfigUseCase",
        _use_case_with_fake_credentials,
    )
    def test_malformed_policy_values_are_rejected_and_row_is_untouched(
        self, _mock_has_password
    ):
        snapshot = self._config_snapshot()
        cases = (
            ("disable_enforcement", {"is_enabled": False}),
            ("at_sign", {"allowed_email_domains": ["user@acme.com"]}),
            ("wildcard", {"allowed_email_domains": ["*.acme.com"]}),
            ("surrounding_whitespace", {"allowed_email_domains": ["   "]}),
            ("empty", {"allowed_email_domains": [""]}),
            ("non_slug_identity_source", {"allowed_sso_providers": ["Okta Acme!"]}),
        )
        for label, data in cases:
            with self.subTest(label=label):
                response = self._patch_sso_settings(data)
                response.render()
                content = json.loads(response.content)

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertTrue(content)
                self.assertEqual(self._config_snapshot(), snapshot)
