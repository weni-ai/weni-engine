from unittest.mock import patch

from django.test import TestCase, override_settings

from connect.api.v1.tests.utils import create_user_and_token
from connect.common.mocks import StripeMockGateway
from connect.common.models import (
    BillingPlan,
    Organization,
    OrganizationRole,
    OrganizationSSOConfig,
)
from connect.usecases.organizations.exceptions import SSOConfigLockoutError
from connect.usecases.organizations.update_sso_config import (
    UpdateOrganizationSSOConfigDTO,
    UpdateOrganizationSSOConfigUseCase,
)


class FakeCredentialsService:
    def __init__(self, has_password=False):
        self._has_password = has_password

    def has_password_credential(self, email):
        return self._has_password


@override_settings(USE_EDA_PERMISSIONS=False)
class UpdateOrganizationSSOConfigUseCaseTestCase(TestCase):
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway):
        mock_get_gateway.return_value = StripeMockGateway()
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

    def execute(self, dto, session_identity_provider, has_password=False):
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

    def test_enabling_raises_lockout_when_actor_has_password(self):
        dto = UpdateOrganizationSSOConfigDTO(is_enabled=True)
        with self.assertRaises(SSOConfigLockoutError):
            self.execute(dto, "google", has_password=True)

    def test_lockout_does_not_persist_config_changes(self):
        dto = UpdateOrganizationSSOConfigDTO(is_enabled=True)
        with self.assertRaises(SSOConfigLockoutError):
            self.execute(dto, None)

        self.assertFalse(
            OrganizationSSOConfig.objects.filter(
                organization=self.organization, is_enabled=True
            ).exists()
        )
