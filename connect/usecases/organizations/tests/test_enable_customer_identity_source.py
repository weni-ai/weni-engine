import uuid
from io import StringIO
from unittest.mock import patch

from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from connect.api.v1.tests.utils import create_user_and_token
from connect.common.mocks import StripeMockGateway
from connect.common.models import (
    BillingPlan,
    Organization,
    OrganizationRole,
    OrganizationSSOConfig,
)
from connect.usecases.organizations.enable_customer_identity_source import (
    EnableCustomerIdentitySourceDTO,
    EnableCustomerIdentitySourceUseCase,
)
from connect.usecases.organizations.exceptions import SSOPolicyValidationError
from connect.usecases.organizations.sso_access import EvaluateOrganizationSSOAccessUseCase
from connect.usecases.organizations.tests.test_sso_access import FakeCredentialsService


LOC_MEM_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "enable-customer-identity-source-tests",
    }
}


def create_organization(name):
    return Organization.objects.create(
        name=name,
        description=name,
        inteligence_organization=1,
        organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
        organization_billing__plan=BillingPlan.PLAN_TRIAL,
    )


@override_settings(
    USE_EDA_PERMISSIONS=False,
    CACHES=LOC_MEM_CACHE,
    SSO_INTERNAL_BYPASS_EMAIL_DOMAINS=["weni.ai", "vtex.com"],
)
class EnableCustomerIdentitySourceUseCaseTestCase(TestCase):
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway):
        mock_get_gateway.return_value = StripeMockGateway()
        cache.clear()
        self.organization = create_organization("Acme Enable Org")
        self.credentials_service = FakeCredentialsService()

    def _execute(self, **overrides):
        defaults = dict(
            organization_uuid=str(self.organization.uuid),
            allowed_sso_providers=["okta-acme"],
            allowed_email_domains=["acme.com"],
            disable=False,
            dry_run=False,
        )
        defaults.update(overrides)
        dto = EnableCustomerIdentitySourceDTO(**defaults)
        return EnableCustomerIdentitySourceUseCase(
            credentials_service=self.credentials_service
        ).execute(dto)

    def _reload_config(self, organization=None):
        organization = organization or self.organization
        return OrganizationSSOConfig.objects.get(organization=organization)

    def _config_snapshot(self, config):
        config.refresh_from_db()
        return (
            config.is_enabled,
            config.requires_customer_identity_source,
            list(config.allowed_email_domains),
            list(config.allowed_sso_providers),
            config.updated_at,
        )

    def test_enablement_sets_marker_and_policy_on_policy_free_organization(self):
        self.assertFalse(
            OrganizationSSOConfig.objects.filter(
                organization=self.organization
            ).exists()
        )

        result = self._execute()

        self.assertTrue(result.persisted)
        self.assertTrue(result.requires_customer_identity_source)
        self.assertTrue(result.is_enabled)
        config = self._reload_config()
        self.assertTrue(config.requires_customer_identity_source)
        self.assertTrue(config.is_enabled)
        self.assertEqual(config.allowed_sso_providers, ["okta-acme"])
        self.assertEqual(config.allowed_email_domains, ["acme.com"])

    def test_idempotent_re_run_leaves_updated_at_unchanged(self):
        self._execute()
        config = self._reload_config()
        snapshot = self._config_snapshot(config)

        result = self._execute()

        self.assertFalse(result.persisted)
        self.assertTrue(result.unchanged)
        self.assertEqual(self._config_snapshot(config), snapshot)

    def test_re_run_with_uppercase_domain_is_a_noop(self):
        self._execute()
        config = self._reload_config()
        snapshot = self._config_snapshot(config)

        result = self._execute(allowed_email_domains=["ACME.COM"])

        self.assertFalse(result.persisted)
        self.assertTrue(result.unchanged)
        self.assertEqual(self._config_snapshot(config), snapshot)
        self.assertEqual(config.allowed_email_domains, ["acme.com"])

    def test_changed_domain_list_replaces_rather_than_appends(self):
        self._execute(
            allowed_email_domains=["acme.com", "acme.com.br"],
        )

        result = self._execute(allowed_email_domains=["acme.com.br"])

        self.assertTrue(result.persisted)
        config = self._reload_config()
        self.assertEqual(config.allowed_email_domains, ["acme.com.br"])
        self.assertNotIn("acme.com", config.allowed_email_domains)

    def test_invalid_input_persists_nothing(self):
        self._execute()
        config = self._reload_config()
        snapshot = self._config_snapshot(config)
        invalid_cases = (
            dict(allowed_email_domains=["@acme.com"]),
            dict(allowed_sso_providers=["Okta Acme!"]),
            dict(allowed_sso_providers=[]),
            dict(allowed_email_domains=[]),
        )

        for overrides in invalid_cases:
            with self.subTest(overrides=overrides):
                with self.assertRaises(SSOPolicyValidationError):
                    self._execute(**overrides)
                self.assertEqual(self._config_snapshot(config), snapshot)

    def test_disable_clears_marker_and_is_enabled_in_one_save(self):
        self._execute()
        save_states = []
        original_save = OrganizationSSOConfig.save

        def tracking_save(instance, *args, **kwargs):
            save_states.append(
                (
                    instance.is_enabled,
                    instance.requires_customer_identity_source,
                    list(instance.allowed_email_domains),
                    list(instance.allowed_sso_providers),
                )
            )
            return original_save(instance, *args, **kwargs)

        with patch.object(OrganizationSSOConfig, "save", tracking_save):
            result = self._execute(
                allowed_sso_providers=[],
                allowed_email_domains=[],
                disable=True,
            )

        self.assertTrue(result.persisted)
        self.assertFalse(result.requires_customer_identity_source)
        self.assertFalse(result.is_enabled)
        self.assertEqual(len(save_states), 1)
        self.assertEqual(
            save_states[0],
            (False, False, ["acme.com"], ["okta-acme"]),
        )
        config = self._reload_config()
        self.assertFalse(config.is_enabled)
        self.assertFalse(config.requires_customer_identity_source)
        self.assertEqual(config.allowed_email_domains, ["acme.com"])
        self.assertEqual(config.allowed_sso_providers, ["okta-acme"])

    def test_domain_conflict_rejected_while_same_source_may_share(self):
        self._execute()
        beta = create_organization("Beta Enable Org")
        second_acme = create_organization("Second Acme Org")

        with self.assertRaises(SSOPolicyValidationError) as raised:
            self._execute(
                organization_uuid=str(beta.uuid),
                allowed_sso_providers=["okta-beta"],
                allowed_email_domains=["acme.com"],
            )

        message = str(raised.exception)
        self.assertIn("already in use", message)
        self.assertNotIn(self.organization.name, message)
        self.assertNotIn(str(self.organization.uuid), message)
        self.assertNotIn("okta-acme", message)
        self.assertFalse(
            OrganizationSSOConfig.objects.filter(organization=beta).exists()
        )

        result = self._execute(
            organization_uuid=str(second_acme.uuid),
            allowed_sso_providers=["okta-acme"],
            allowed_email_domains=["acme.com"],
        )

        self.assertTrue(result.persisted)
        shared = self._reload_config(second_acme)
        self.assertTrue(shared.requires_customer_identity_source)
        self.assertEqual(shared.allowed_email_domains, ["acme.com"])
        self.assertEqual(shared.allowed_sso_providers, ["okta-acme"])

    def test_two_customers_do_not_open_each_others_organization(self):
        beta = create_organization("Beta Isolation Org")
        acme_user, _ = create_user_and_token("acme_member")
        acme_user.email = "maria@acme.com"
        acme_user.save(update_fields=["email"])
        beta_user, _ = create_user_and_token("beta_member")
        beta_user.email = "bob@beta.com"
        beta_user.save(update_fields=["email"])

        for organization, user in (
            (self.organization, acme_user),
            (self.organization, beta_user),
            (beta, acme_user),
            (beta, beta_user),
        ):
            organization.authorizations.create(
                user=user, role=OrganizationRole.ADMIN.value
            )

        self._execute()
        self._execute(
            organization_uuid=str(beta.uuid),
            allowed_sso_providers=["okta-beta"],
            allowed_email_domains=["beta.com"],
        )

        self.assertEqual(
            OrganizationSSOConfig.objects.filter(
                requires_customer_identity_source=True
            ).count(),
            2,
        )

        evaluator = EvaluateOrganizationSSOAccessUseCase(
            credentials_service=self.credentials_service
        )
        self.assertTrue(
            evaluator.execute(self.organization, acme_user, "okta-acme")
        )
        self.assertFalse(evaluator.execute(beta, acme_user, "okta-acme"))
        self.assertTrue(evaluator.execute(beta, beta_user, "okta-beta"))
        self.assertFalse(
            evaluator.execute(self.organization, beta_user, "okta-beta")
        )


@override_settings(
    USE_EDA_PERMISSIONS=False,
    CACHES=LOC_MEM_CACHE,
    SSO_INTERNAL_BYPASS_EMAIL_DOMAINS=["weni.ai", "vtex.com"],
)
class EnableCustomerIdentitySourceCommandTestCase(TestCase):
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway):
        mock_get_gateway.return_value = StripeMockGateway()
        cache.clear()
        self.organization = create_organization("Acme Command Org")

    def _call(self, *args):
        out = StringIO()
        call_command("enable_customer_identity_source", *args, stdout=out)
        return out.getvalue()

    def test_command_parses_repeatable_flags(self):
        output = self._call(
            "--organization",
            str(self.organization.uuid),
            "--identity-source",
            "okta-acme",
            "--email-domain",
            "acme.com",
            "--email-domain",
            "acme.com.br",
        )

        config = OrganizationSSOConfig.objects.get(organization=self.organization)
        self.assertTrue(config.requires_customer_identity_source)
        self.assertTrue(config.is_enabled)
        self.assertEqual(config.allowed_sso_providers, ["okta-acme"])
        self.assertEqual(config.allowed_email_domains, ["acme.com", "acme.com.br"])
        self.assertIn(str(self.organization.uuid), output)
        self.assertIn("okta-acme", output)
        self.assertIn("acme.com", output)
        self.assertIn("acme.com.br", output)

    def test_command_dry_run_persists_nothing(self):
        output = self._call(
            "--organization",
            str(self.organization.uuid),
            "--identity-source",
            "okta-acme",
            "--email-domain",
            "acme.com",
            "--dry-run",
        )

        self.assertFalse(
            OrganizationSSOConfig.objects.filter(
                organization=self.organization
            ).exists()
        )
        self.assertIn("not persisted", output)
        self.assertIn("okta-acme", output)
        self.assertIn("acme.com", output)

    def test_command_unknown_organization_uuid_raises_command_error(self):
        missing = str(uuid.uuid4())
        with self.assertRaises(CommandError) as raised:
            self._call(
                "--organization",
                missing,
                "--identity-source",
                "okta-acme",
                "--email-domain",
                "acme.com",
            )

        self.assertIn(missing, str(raised.exception))
        self.assertFalse(OrganizationSSOConfig.objects.exists())

    def test_command_validation_failure_raises_command_error(self):
        with self.assertRaises(CommandError):
            self._call(
                "--organization",
                str(self.organization.uuid),
                "--identity-source",
                "Okta Acme!",
                "--email-domain",
                "acme.com",
            )

        self.assertFalse(
            OrganizationSSOConfig.objects.filter(
                organization=self.organization
            ).exists()
        )

    def test_domain_conflict_command_output_does_not_name_holder_or_carry_secret(self):
        holder_source = "okta-holder-secret-name"
        self._call(
            "--organization",
            str(self.organization.uuid),
            "--identity-source",
            holder_source,
            "--email-domain",
            "acme.com",
        )
        beta = create_organization("Beta Conflict Org")
        stdout = StringIO()
        stderr = StringIO()
        with self.assertRaises(CommandError) as raised:
            call_command(
                "enable_customer_identity_source",
                "--organization",
                str(beta.uuid),
                "--identity-source",
                "okta-beta",
                "--email-domain",
                "acme.com",
                stdout=stdout,
                stderr=stderr,
            )

        message = str(raised.exception)
        output = stdout.getvalue() + stderr.getvalue() + message
        self.assertIn("already in use", message)
        self.assertNotIn(self.organization.name, output)
        self.assertNotIn(str(self.organization.uuid), output)
        self.assertNotIn(holder_source, output)
        self.assertFalse(
            OrganizationSSOConfig.objects.filter(organization=beta).exists()
        )
