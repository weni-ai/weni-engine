import importlib
import uuid
from unittest.mock import patch

from django.core.cache import cache
from django.db import migrations
from django.test import SimpleTestCase, TestCase, override_settings

from connect.api.v1.tests.utils import create_user_and_token
from connect.common.mocks import StripeMockGateway
from connect.common.models import (
    BillingPlan,
    Organization,
    OrganizationRole,
    OrganizationSSOConfig,
    Project,
)
from connect.usecases.organizations.sso_access import (
    BROKER_ALIAS_TO_PROVIDER,
    BuildOrganizationSSOAccessMapUseCase,
    EvaluateOrganizationSSOAccessUseCase,
    ExcludeNonCompliantOrganizationProjectsUseCase,
    OrganizationSSOAccessDisabledReason,
    enrich_serializer_context_with_sso_access,
    is_sso_internal_bypass_email,
    resolve_sso_provider,
)

LOC_MEM_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "sso-access-tests",
    }
}

HAS_PASSWORD_CREDENTIAL = (
    "connect.services.keycloak.service.KeycloakCredentialsService."
    "has_password_credential"
)


class FakeCredentialsService:
    def __init__(self, has_password=False):
        self._has_password = has_password
        self.calls = []

    def has_password_credential(self, email):
        self.calls.append(email)
        return self._has_password


def create_organization(name):
    return Organization.objects.create(
        name=name,
        description=name,
        inteligence_organization=1,
        organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
        organization_billing__plan=BillingPlan.PLAN_TRIAL,
    )


class ResolveSSOProviderTestCase(TestCase):
    def test_returns_none_without_alias(self):
        self.assertIsNone(resolve_sso_provider(None))
        self.assertIsNone(resolve_sso_provider(""))

    def test_maps_known_aliases_to_canonical_providers(self):
        self.assertEqual(resolve_sso_provider("Google"), "google")
        self.assertEqual(resolve_sso_provider("azure-ad"), "microsoft")
        self.assertEqual(resolve_sso_provider("entra-id"), "microsoft")

    def test_returns_unknown_alias_lowercased(self):
        self.assertEqual(resolve_sso_provider("Okta"), "okta")

    def test_broker_alias_map_contains_no_multi_tenant_vendor_family(self):
        self.assertEqual(
            set(BROKER_ALIAS_TO_PROVIDER),
            {
                "google",
                "microsoft",
                "azure-ad",
                "azuread",
                "entra-id",
                "office365",
            },
        )
        self.assertEqual(resolve_sso_provider("okta-acme"), "okta-acme")
        self.assertNotEqual(resolve_sso_provider("okta-acme"), "okta")


@override_settings(USE_EDA_PERMISSIONS=False)
class EvaluateOrganizationSSOAccessUseCaseTestCase(TestCase):
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway):
        mock_get_gateway.return_value = StripeMockGateway()
        self.user, _ = create_user_and_token("sso_eval_user")
        self.organization = create_organization("SSO Eval Org")
        self.organization.authorizations.create(
            user=self.user, role=OrganizationRole.ADMIN.value
        )

    def create_sso_config(self, **kwargs):
        return OrganizationSSOConfig.objects.create(
            organization=self.organization, **kwargs
        )

    def evaluate(self, session_identity_provider, has_password=False):
        usecase = EvaluateOrganizationSSOAccessUseCase(
            credentials_service=FakeCredentialsService(has_password=has_password)
        )
        return usecase.evaluate(self.organization, self.user, session_identity_provider)

    def execute(self, session_identity_provider, has_password=False):
        return self.evaluate(session_identity_provider, has_password).is_compliant

    def test_allows_organization_without_sso_config(self):
        self.assertTrue(self.execute("google"))

    def test_allows_organization_with_disabled_sso_config(self):
        self.create_sso_config(is_enabled=False)
        self.assertTrue(self.execute(None))

    def test_blocks_non_sso_session(self):
        self.create_sso_config(is_enabled=True)
        result = self.evaluate(None)
        self.assertFalse(result.is_compliant)
        self.assertEqual(
            result.disabled_reason,
            OrganizationSSOAccessDisabledReason.SSO_SESSION_REQUIRED.value,
        )

    def test_blocks_provider_not_in_allowlist(self):
        self.create_sso_config(is_enabled=True, allowed_sso_providers=["microsoft"])
        result = self.evaluate("google")
        self.assertFalse(result.is_compliant)
        self.assertEqual(
            result.disabled_reason,
            OrganizationSSOAccessDisabledReason.SSO_PROVIDER_NOT_ALLOWED.value,
        )

    def test_allows_any_provider_when_allowlist_is_empty(self):
        self.create_sso_config(is_enabled=True, allowed_sso_providers=[])
        self.assertTrue(self.execute("google"))

    def test_blocks_email_domain_not_in_allowlist(self):
        self.create_sso_config(is_enabled=True, allowed_email_domains=["weni.ai"])
        result = self.evaluate("google")
        self.assertFalse(result.is_compliant)
        self.assertEqual(
            result.disabled_reason,
            OrganizationSSOAccessDisabledReason.SSO_EMAIL_DOMAIN_NOT_ALLOWED.value,
        )

    def test_allows_email_domain_in_allowlist_case_insensitively(self):
        self.create_sso_config(is_enabled=True, allowed_email_domains=["USER.com"])
        self.assertTrue(self.execute("google"))

    def test_blocks_user_with_password_credential(self):
        self.create_sso_config(is_enabled=True)
        result = self.evaluate("google", has_password=True)
        self.assertFalse(result.is_compliant)
        self.assertEqual(
            result.disabled_reason,
            OrganizationSSOAccessDisabledReason.SSO_PASSWORD_CONFIGURED.value,
        )

    def test_blocks_when_credential_state_is_unknown(self):
        self.create_sso_config(is_enabled=True)
        result = self.evaluate("google", has_password=None)
        self.assertFalse(result.is_compliant)
        self.assertEqual(
            result.disabled_reason,
            OrganizationSSOAccessDisabledReason.SSO_CREDENTIAL_UNAVAILABLE.value,
        )

    def test_allows_fully_compliant_user(self):
        self.create_sso_config(
            is_enabled=True,
            allowed_email_domains=["user.com"],
            allowed_sso_providers=["google"],
        )
        result = self.evaluate("google")
        self.assertTrue(result.is_compliant)
        self.assertIsNone(result.disabled_reason)

    def test_allows_internal_bypass_domain_without_sso_session(self):
        self.user.email = "staff@weni.ai"
        self.user.save(update_fields=["email"])
        self.create_sso_config(
            is_enabled=True,
            allowed_email_domains=["customer.com"],
            allowed_sso_providers=["microsoft"],
        )
        result = self.evaluate(None, has_password=True)
        self.assertTrue(result.is_compliant)
        self.assertIsNone(result.disabled_reason)

    def test_allows_vtex_internal_bypass_domain(self):
        self.user.email = "staff@vtex.com"
        self.user.save(update_fields=["email"])
        self.create_sso_config(
            is_enabled=True,
            allowed_email_domains=["customer.com"],
        )
        result = self.evaluate(None, has_password=True)
        self.assertTrue(result.is_compliant)

    @override_settings(SSO_INTERNAL_BYPASS_EMAIL_DOMAINS=[])
    def test_blocks_internal_domain_when_bypass_list_is_empty(self):
        self.user.email = "staff@weni.ai"
        self.user.save(update_fields=["email"])
        self.create_sso_config(is_enabled=True)
        result = self.evaluate(None)
        self.assertFalse(result.is_compliant)
        self.assertEqual(
            result.disabled_reason,
            OrganizationSSOAccessDisabledReason.SSO_SESSION_REQUIRED.value,
        )

    def test_memoizes_credential_lookup_per_email(self):
        self.create_sso_config(is_enabled=True)
        credentials_service = FakeCredentialsService(has_password=False)
        usecase = EvaluateOrganizationSSOAccessUseCase(
            credentials_service=credentials_service
        )

        usecase.execute(self.organization, self.user, "google")
        usecase.execute(self.organization, self.user, "google")

        self.assertEqual(len(credentials_service.calls), 1)


@override_settings(
    USE_EDA_PERMISSIONS=False,
    CACHES=LOC_MEM_CACHE,
    SSO_INTERNAL_BYPASS_EMAIL_DOMAINS=["weni.ai", "vtex.com"],
)
class CustomerIdentitySourceAccessTestCase(TestCase):
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway):
        mock_get_gateway.return_value = StripeMockGateway()
        cache.clear()
        self.user, _ = create_user_and_token("sso_acme_user")
        self.user.email = "Maria@ACME.com"
        self.user.save(update_fields=["email"])

        self.organization = create_organization("Acme")
        self.organization.authorizations.create(
            user=self.user, role=OrganizationRole.ADMIN.value
        )
        OrganizationSSOConfig.objects.create(
            organization=self.organization,
            is_enabled=True,
            allowed_sso_providers=["okta-acme"],
            allowed_email_domains=["acme.com"],
            requires_customer_identity_source=True,
        )

        self.beta_organization = create_organization("Beta")
        OrganizationSSOConfig.objects.create(
            organization=self.beta_organization,
            is_enabled=True,
            allowed_sso_providers=["okta-beta"],
            allowed_email_domains=["acme.com"],
            requires_customer_identity_source=True,
        )

        self.policy_free_organization = create_organization("Side Project")
        self.policy_free_organization.authorizations.create(
            user=self.user, role=OrganizationRole.ADMIN.value
        )

    def evaluate(
        self, organization, session_identity_provider, has_password=False, user=None
    ):
        usecase = EvaluateOrganizationSSOAccessUseCase(
            credentials_service=FakeCredentialsService(has_password=has_password)
        )
        return usecase.evaluate(
            organization, user or self.user, session_identity_provider
        )

    def test_evaluation_matrix_admits_only_the_matching_customer_source(self):
        cases = (
            ("okta-acme", True, None),
            (
                "okta-beta",
                False,
                OrganizationSSOAccessDisabledReason.SSO_PROVIDER_NOT_ALLOWED.value,
            ),
            (
                "google",
                False,
                OrganizationSSOAccessDisabledReason.SSO_PROVIDER_NOT_ALLOWED.value,
            ),
            (
                "microsoft",
                False,
                OrganizationSSOAccessDisabledReason.SSO_PROVIDER_NOT_ALLOWED.value,
            ),
            (
                "github",
                False,
                OrganizationSSOAccessDisabledReason.SSO_PROVIDER_NOT_ALLOWED.value,
            ),
            (
                None,
                False,
                OrganizationSSOAccessDisabledReason.SSO_SESSION_REQUIRED.value,
            ),
        )
        for session, is_compliant, disabled_reason in cases:
            with self.subTest(session=session):
                result = self.evaluate(self.organization, session)
                self.assertEqual(result.is_compliant, is_compliant)
                self.assertEqual(result.disabled_reason, disabled_reason)

    def test_customer_identity_sources_do_not_alias_across_tenants(self):
        beta_on_acme = self.evaluate(self.organization, "okta-beta")
        self.assertFalse(beta_on_acme.is_compliant)
        self.assertEqual(
            beta_on_acme.disabled_reason,
            OrganizationSSOAccessDisabledReason.SSO_PROVIDER_NOT_ALLOWED.value,
        )

        acme_on_beta = self.evaluate(self.beta_organization, "okta-acme")
        self.assertFalse(acme_on_beta.is_compliant)
        self.assertEqual(
            acme_on_beta.disabled_reason,
            OrganizationSSOAccessDisabledReason.SSO_PROVIDER_NOT_ALLOWED.value,
        )

    def test_satisfying_session_refused_when_password_configured(self):
        result = self.evaluate(self.organization, "okta-acme", has_password=True)
        self.assertFalse(result.is_compliant)
        self.assertEqual(
            result.disabled_reason,
            OrganizationSSOAccessDisabledReason.SSO_PASSWORD_CONFIGURED.value,
        )

    def test_satisfying_session_refused_when_credential_state_unknown(self):
        result = self.evaluate(self.organization, "okta-acme", has_password=None)
        self.assertFalse(result.is_compliant)
        self.assertEqual(
            result.disabled_reason,
            OrganizationSSOAccessDisabledReason.SSO_CREDENTIAL_UNAVAILABLE.value,
        )

    def test_dual_membership_keeps_policy_free_org_active_on_refused_session(self):
        credentials_service = FakeCredentialsService(has_password=False)
        usecase = EvaluateOrganizationSSOAccessUseCase(
            credentials_service=credentials_service
        )
        session = "okta-beta"
        marked = usecase.evaluate(self.organization, self.user, session)
        policy_free = usecase.evaluate(
            self.policy_free_organization, self.user, session
        )

        self.assertFalse(marked.is_compliant)
        self.assertEqual(
            marked.disabled_reason,
            OrganizationSSOAccessDisabledReason.SSO_PROVIDER_NOT_ALLOWED.value,
        )
        self.assertTrue(policy_free.is_compliant)
        self.assertIsNone(policy_free.disabled_reason)

    def test_email_domain_match_is_case_insensitive_and_not_a_suffix(self):
        matching = self.evaluate(self.organization, "okta-acme")
        self.assertTrue(matching.is_compliant)
        self.assertIsNone(matching.disabled_reason)

        self.user.email = "maria@mail.acme.com"
        self.user.save(update_fields=["email"])
        subdomain_email = self.evaluate(self.organization, "okta-acme")
        self.assertFalse(subdomain_email.is_compliant)
        self.assertEqual(
            subdomain_email.disabled_reason,
            OrganizationSSOAccessDisabledReason.SSO_EMAIL_DOMAIN_NOT_ALLOWED.value,
        )

        self.user.email = "maria@acme.com"
        self.user.save(update_fields=["email"])
        config = self.organization.sso_config
        config.allowed_email_domains = ["mail.acme.com"]
        config.save(update_fields=["allowed_email_domains"])
        parent_domain_not_in_subdomain_allowlist = self.evaluate(
            self.organization, "okta-acme"
        )
        self.assertFalse(parent_domain_not_in_subdomain_allowlist.is_compliant)
        self.assertEqual(
            parent_domain_not_in_subdomain_allowlist.disabled_reason,
            OrganizationSSOAccessDisabledReason.SSO_EMAIL_DOMAIN_NOT_ALLOWED.value,
        )

    @override_settings(SSO_INTERNAL_BYPASS_EMAIL_DOMAINS=["weni.ai", "vtex.com"])
    def test_support_domain_matrix_on_customer_bound_password_session(self):
        cases = (
            ("staff@weni.ai", True),
            ("staff@vtex.com", True),
            ("staff@notweni.ai", False),
            ("staff@vtex.com.br", False),
            ("staff@partner.com", False),
        )
        for index, (email, admitted) in enumerate(cases):
            with self.subTest(email=email):
                member, _ = create_user_and_token(f"support_matrix_{index}")
                member.email = email
                member.save(update_fields=["email"])
                result = self.evaluate(
                    self.organization, None, has_password=True, user=member
                )
                if admitted:
                    self.assertTrue(result.is_compliant)
                    self.assertIsNone(result.disabled_reason)
                else:
                    self.assertFalse(result.is_compliant)


SSO_ACCESS_LOGGER = "connect.usecases.organizations.sso_access"


@override_settings(
    USE_EDA_PERMISSIONS=False,
    CACHES=LOC_MEM_CACHE,
    SSO_INTERNAL_BYPASS_EMAIL_DOMAINS=["weni.ai", "vtex.com"],
)
class IncompletePolicyAccessTestCase(TestCase):
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway):
        mock_get_gateway.return_value = StripeMockGateway()
        cache.clear()
        self.user, _ = create_user_and_token("sso_incomplete_user")
        self.user.email = "Maria@ACME.com"
        self.user.save(update_fields=["email"])

        self.outsider, _ = create_user_and_token("sso_incomplete_outsider")
        self.outsider.email = "other@elsewhere.com"
        self.outsider.save(update_fields=["email"])

        self.marked_incomplete = self._create_org_with_sso(
            "Marked incomplete",
            is_enabled=True,
            allowed_sso_providers=[],
            allowed_email_domains=[],
            requires_customer_identity_source=True,
        )
        self.unmarked_legacy = self._create_org_with_sso(
            "Unmarked legacy",
            is_enabled=True,
            allowed_sso_providers=[],
            allowed_email_domains=[],
        )
        self.marked_complete = self._create_org_with_sso(
            "Marked complete",
            is_enabled=True,
            allowed_sso_providers=["okta-acme"],
            allowed_email_domains=["acme.com"],
            requires_customer_identity_source=True,
        )

    def _create_org_with_sso(self, name, **sso_kwargs):
        organization = create_organization(name)
        OrganizationSSOConfig.objects.create(organization=organization, **sso_kwargs)
        return organization

    def evaluate(
        self, organization, session_identity_provider, has_password=False, user=None
    ):
        usecase = EvaluateOrganizationSSOAccessUseCase(
            credentials_service=FakeCredentialsService(has_password=has_password)
        )
        return usecase.evaluate(
            organization, user or self.user, session_identity_provider
        )

    def test_marked_org_with_either_list_empty_denies_as_incomplete_policy(self):
        variants = (
            {"allowed_sso_providers": [], "allowed_email_domains": ["acme.com"]},
            {"allowed_sso_providers": ["okta-acme"], "allowed_email_domains": []},
            {"allowed_sso_providers": [], "allowed_email_domains": []},
        )
        for index, lists in enumerate(variants):
            organization = self._create_org_with_sso(
                f"Marked empty list {index}",
                is_enabled=True,
                requires_customer_identity_source=True,
                **lists,
            )
            with self.subTest(**lists):
                result = self.evaluate(organization, "google")
                self.assertFalse(result.is_compliant)
                self.assertEqual(
                    result.disabled_reason,
                    OrganizationSSOAccessDisabledReason.SSO_POLICY_INCOMPLETE.value,
                )

    def test_unmarked_org_with_identical_inputs_returns_pre_delivery_outcome(self):
        google = self.evaluate(self.unmarked_legacy, "google")
        self.assertTrue(google.is_compliant)
        self.assertIsNone(google.disabled_reason)

        no_source = self.evaluate(self.unmarked_legacy, None)
        self.assertFalse(no_source.is_compliant)
        self.assertEqual(
            no_source.disabled_reason,
            OrganizationSSOAccessDisabledReason.SSO_SESSION_REQUIRED.value,
        )

    def test_incomplete_policy_does_not_call_credentials_service(self):
        credentials_service = FakeCredentialsService(has_password=False)
        usecase = EvaluateOrganizationSSOAccessUseCase(
            credentials_service=credentials_service
        )
        result = usecase.evaluate(
            self.marked_incomplete, self.user, "okta-acme"
        )
        self.assertFalse(result.is_compliant)
        self.assertEqual(
            result.disabled_reason,
            OrganizationSSOAccessDisabledReason.SSO_POLICY_INCOMPLETE.value,
        )
        self.assertEqual(credentials_service.calls, [])

    def test_every_refusal_logs_organization_member_and_resolved_source(self):
        cases = (
            (
                self.marked_incomplete,
                self.user,
                "okta-acme",
                False,
                OrganizationSSOAccessDisabledReason.SSO_POLICY_INCOMPLETE,
                "WARNING",
                "okta-acme",
            ),
            (
                self.marked_complete,
                self.user,
                None,
                False,
                OrganizationSSOAccessDisabledReason.SSO_SESSION_REQUIRED,
                "INFO",
                None,
            ),
            (
                self.marked_complete,
                self.user,
                "google",
                False,
                OrganizationSSOAccessDisabledReason.SSO_PROVIDER_NOT_ALLOWED,
                "INFO",
                "google",
            ),
            (
                self.marked_complete,
                self.outsider,
                "okta-acme",
                False,
                OrganizationSSOAccessDisabledReason.SSO_EMAIL_DOMAIN_NOT_ALLOWED,
                "INFO",
                "okta-acme",
            ),
            (
                self.marked_complete,
                self.user,
                "okta-acme",
                True,
                OrganizationSSOAccessDisabledReason.SSO_PASSWORD_CONFIGURED,
                "INFO",
                "okta-acme",
            ),
            (
                self.marked_complete,
                self.user,
                "okta-acme",
                None,
                OrganizationSSOAccessDisabledReason.SSO_CREDENTIAL_UNAVAILABLE,
                "INFO",
                "okta-acme",
            ),
        )
        self.assertEqual(len(cases), 6)
        warning_reasons = []
        info_reasons = []
        for (
            organization,
            user,
            session,
            has_password,
            reason,
            level,
            resolved_source,
        ) in cases:
            with self.subTest(reason=reason.value):
                with self.assertLogs(SSO_ACCESS_LOGGER, level="INFO") as captured:
                    result = self.evaluate(
                        organization, session, has_password=has_password, user=user
                    )
                self.assertEqual(result.disabled_reason, reason.value)
                self.assertEqual(len(captured.records), 1)
                record = captured.records[0]
                self.assertEqual(record.levelname, level)
                message = record.getMessage()
                self.assertIn(str(organization.uuid), message)
                self.assertIn(user.email, message)
                self.assertIn(f"identity_source={resolved_source}", message)
                if level == "WARNING":
                    warning_reasons.append(reason.value)
                else:
                    info_reasons.append(reason.value)
        self.assertEqual(
            warning_reasons,
            [OrganizationSSOAccessDisabledReason.SSO_POLICY_INCOMPLETE.value],
        )
        self.assertEqual(
            info_reasons,
            [
                OrganizationSSOAccessDisabledReason.SSO_SESSION_REQUIRED.value,
                OrganizationSSOAccessDisabledReason.SSO_PROVIDER_NOT_ALLOWED.value,
                OrganizationSSOAccessDisabledReason.SSO_EMAIL_DOMAIN_NOT_ALLOWED.value,
                OrganizationSSOAccessDisabledReason.SSO_PASSWORD_CONFIGURED.value,
                OrganizationSSOAccessDisabledReason.SSO_CREDENTIAL_UNAVAILABLE.value,
            ],
        )

    def test_refusal_logs_and_results_do_not_leak_secrets_or_other_org_configuration(
        self,
    ):
        holder_source = "okta-holder-secret-name"
        other = self._create_org_with_sso(
            "Beta Tenant Secret Holder",
            is_enabled=True,
            allowed_sso_providers=[holder_source],
            allowed_email_domains=["beta-secret.example"],
            requires_customer_identity_source=True,
        )
        leak_tokens = (
            str(other.uuid),
            other.name,
            holder_source,
            "beta-secret.example",
        )
        named_in_reason = (
            "okta",
            "google",
            "microsoft",
            "github",
            "customer",
            "tenant",
        )
        cases = (
            (
                self.marked_incomplete,
                self.user,
                "okta-acme",
                False,
                OrganizationSSOAccessDisabledReason.SSO_POLICY_INCOMPLETE,
            ),
            (
                self.marked_complete,
                self.user,
                None,
                False,
                OrganizationSSOAccessDisabledReason.SSO_SESSION_REQUIRED,
            ),
            (
                self.marked_complete,
                self.user,
                "google",
                False,
                OrganizationSSOAccessDisabledReason.SSO_PROVIDER_NOT_ALLOWED,
            ),
            (
                self.marked_complete,
                self.outsider,
                "okta-acme",
                False,
                OrganizationSSOAccessDisabledReason.SSO_EMAIL_DOMAIN_NOT_ALLOWED,
            ),
            (
                self.marked_complete,
                self.user,
                "okta-acme",
                True,
                OrganizationSSOAccessDisabledReason.SSO_PASSWORD_CONFIGURED,
            ),
            (
                self.marked_complete,
                self.user,
                "okta-acme",
                None,
                OrganizationSSOAccessDisabledReason.SSO_CREDENTIAL_UNAVAILABLE,
            ),
        )
        self.assertEqual(len(cases), 6)
        for organization, user, session, has_password, reason in cases:
            with self.subTest(reason=reason.value):
                with self.assertLogs(SSO_ACCESS_LOGGER, level="INFO") as captured:
                    result = self.evaluate(
                        organization, session, has_password=has_password, user=user
                    )
                self.assertEqual(result.disabled_reason, reason.value)
                self.assertEqual(
                    set(result.__dict__),
                    {"is_compliant", "disabled_reason"},
                )
                message = captured.records[0].getMessage()
                for token in leak_tokens:
                    self.assertNotIn(token, message)
                    self.assertNotIn(token, result.disabled_reason)
                for named in named_in_reason:
                    self.assertNotIn(named, result.disabled_reason)

    def test_legacy_row_keeps_default_marker_and_evaluates_as_pre_delivery(self):
        config = self.unmarked_legacy.sso_config
        snapshot = (
            config.is_enabled,
            config.allowed_email_domains,
            config.allowed_sso_providers,
            config.uuid,
        )
        self.assertFalse(config.requires_customer_identity_source)
        config.refresh_from_db()
        self.assertEqual(
            (
                config.is_enabled,
                config.allowed_email_domains,
                config.allowed_sso_providers,
                config.uuid,
            ),
            snapshot,
        )

        google = self.evaluate(self.unmarked_legacy, "google")
        self.assertTrue(google.is_compliant)
        self.assertIsNone(google.disabled_reason)

        no_source = self.evaluate(self.unmarked_legacy, None)
        self.assertFalse(no_source.is_compliant)
        self.assertEqual(
            no_source.disabled_reason,
            OrganizationSSOAccessDisabledReason.SSO_SESSION_REQUIRED.value,
        )

    def test_support_domain_is_admitted_when_policy_is_incomplete(self):
        """A reviewer preferring the literal reading of FR-005 reverses
        the decision by moving one line in evaluate.
        """
        self.user.email = "staff@weni.ai"
        self.user.save(update_fields=["email"])
        result = self.evaluate(
            self.marked_incomplete, None, has_password=True
        )
        self.assertTrue(result.is_compliant)
        self.assertIsNone(result.disabled_reason)


class IsSSOInternalBypassEmailTestCase(TestCase):
    def test_matches_default_bypass_domains_case_insensitively(self):
        self.assertTrue(is_sso_internal_bypass_email("staff@weni.ai"))
        self.assertTrue(is_sso_internal_bypass_email("staff@WENI.AI"))
        self.assertTrue(is_sso_internal_bypass_email("staff@vtex.com"))

    def test_rejects_non_bypass_domains(self):
        self.assertFalse(is_sso_internal_bypass_email("staff@user.com"))
        self.assertFalse(is_sso_internal_bypass_email(""))
        self.assertFalse(is_sso_internal_bypass_email("not-an-email"))

    @override_settings(SSO_INTERNAL_BYPASS_EMAIL_DOMAINS=["custom.io"])
    def test_uses_settings_override(self):
        self.assertTrue(is_sso_internal_bypass_email("a@custom.io"))
        self.assertFalse(is_sso_internal_bypass_email("staff@weni.ai"))


@override_settings(USE_EDA_PERMISSIONS=False)
class BuildOrganizationSSOAccessMapUseCaseTestCase(TestCase):
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway):
        mock_get_gateway.return_value = StripeMockGateway()
        self.user, _ = create_user_and_token("sso_filter_user")

        self.enforcing_org = create_organization("Enforcing Org")
        self.enforcing_org.authorizations.create(
            user=self.user, role=OrganizationRole.ADMIN.value
        )
        OrganizationSSOConfig.objects.create(
            organization=self.enforcing_org, is_enabled=True
        )

        self.open_org = create_organization("Open Org")
        self.open_org.authorizations.create(
            user=self.user, role=OrganizationRole.ADMIN.value
        )

    def build_map(self, session_identity_provider, has_password=False):
        credentials_service = FakeCredentialsService(has_password=has_password)
        usecase = BuildOrganizationSSOAccessMapUseCase(
            evaluate_usecase=EvaluateOrganizationSSOAccessUseCase(
                credentials_service=credentials_service
            )
        )
        queryset = Organization.objects.filter(
            uuid__in=[self.enforcing_org.uuid, self.open_org.uuid]
        )
        result = usecase.execute(queryset, self.user, session_identity_provider)
        self.credentials_service = credentials_service
        return result

    def test_maps_disabled_reason_for_non_compliant_session(self):
        access_map = self.build_map(None)
        self.assertIn(self.enforcing_org.pk, access_map)
        self.assertFalse(access_map[self.enforcing_org.pk].is_compliant)
        self.assertEqual(
            access_map[self.enforcing_org.pk].disabled_reason,
            OrganizationSSOAccessDisabledReason.SSO_SESSION_REQUIRED.value,
        )
        self.assertNotIn(self.open_org.pk, access_map)

    def test_maps_compliant_enforcing_org(self):
        access_map = self.build_map("google")
        self.assertTrue(access_map[self.enforcing_org.pk].is_compliant)
        self.assertNotIn(self.open_org.pk, access_map)

    def test_does_not_query_credentials_for_non_sso_session(self):
        self.build_map(None)
        self.assertEqual(self.credentials_service.calls, [])


@override_settings(USE_EDA_PERMISSIONS=False)
class ExcludeNonCompliantOrganizationProjectsUseCaseTestCase(TestCase):
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway):
        mock_get_gateway.return_value = StripeMockGateway()
        self.user, _ = create_user_and_token("sso_exclude_projects_user")

        self.enforcing_org = create_organization("Exclude Enforcing Org")
        self.enforcing_org.authorizations.create(
            user=self.user, role=OrganizationRole.ADMIN.value
        )
        OrganizationSSOConfig.objects.create(
            organization=self.enforcing_org, is_enabled=True
        )

        self.open_org = create_organization("Exclude Open Org")
        self.open_org.authorizations.create(
            user=self.user, role=OrganizationRole.ADMIN.value
        )

        self.enforcing_project = Project.objects.create(
            name="Exclude Enforcing Project",
            flow_organization=uuid.uuid4(),
            organization=self.enforcing_org,
        )
        self.open_project = Project.objects.create(
            name="Exclude Open Project",
            flow_organization=uuid.uuid4(),
            organization=self.open_org,
        )

    def execute(self, session_identity_provider):
        queryset = Project.objects.filter(
            pk__in=[self.enforcing_project.pk, self.open_project.pk]
        )
        return ExcludeNonCompliantOrganizationProjectsUseCase().execute(
            queryset, self.user, session_identity_provider
        )

    def test_excludes_projects_from_non_compliant_enforcing_org(self):
        result = self.execute(None)
        result_pks = set(result.values_list("pk", flat=True))
        self.assertEqual(result_pks, {self.open_project.pk})

    @patch(HAS_PASSWORD_CREDENTIAL, return_value=False)
    def test_keeps_all_projects_for_compliant_session(self, _mock_has_password):
        result = self.execute("google")
        result_pks = set(result.values_list("pk", flat=True))
        self.assertEqual(result_pks, {self.enforcing_project.pk, self.open_project.pk})


@override_settings(USE_EDA_PERMISSIONS=False)
class EnrichSerializerContextWithSSOAccessTestCase(TestCase):
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway):
        mock_get_gateway.return_value = StripeMockGateway()
        self.user, _ = create_user_and_token("sso_enrich_user")

        self.enforcing_org = create_organization("Enrich Enforcing Org")
        OrganizationSSOConfig.objects.create(
            organization=self.enforcing_org, is_enabled=True
        )

    def test_retrieve_evaluates_sso_for_org_outside_membership_queryset(self):
        class FakeView:
            action = "retrieve"
            kwargs = {"uuid": str(self.enforcing_org.uuid)}

            def get_queryset(self):
                return Organization.objects.none()

        view = FakeView()
        view.request = type(
            "Request",
            (),
            {"user": self.user, "session_identity_provider": None},
        )()

        context = enrich_serializer_context_with_sso_access(view, {})
        result = context["sso_access_results"][self.enforcing_org.pk]

        self.assertFalse(result.is_compliant)
        self.assertEqual(
            result.disabled_reason,
            OrganizationSSOAccessDisabledReason.SSO_SESSION_REQUIRED.value,
        )


class OrganizationSSOConfigMarkerMigrationTestCase(SimpleTestCase):
    def test_migration_0100_operations_are_addfield_and_not_runpython(self):
        module = importlib.import_module(
            "connect.common.migrations."
            "0100_organizationssoconfig_requires_customer_identity_source"
        )

        operations = module.Migration.operations
        self.assertTrue(operations)
        for operation in operations:
            self.assertIsInstance(operation, migrations.AddField)
            self.assertNotIsInstance(operation, migrations.RunPython)
