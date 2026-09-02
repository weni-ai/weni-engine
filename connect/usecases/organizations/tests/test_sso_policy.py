from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings

from connect.common.mocks import StripeMockGateway
from connect.common.models import BillingPlan, Organization, OrganizationSSOConfig
from connect.usecases.organizations.exceptions import SSOPolicyValidationError
from connect.usecases.organizations.sso_policy import (
    OrganizationSSOPolicyDTO,
    ValidateOrganizationSSOPolicyUseCase,
    normalize_email_domain,
    normalize_identity_source,
)


LOC_MEM_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "sso-policy-tests",
    }
}


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


def _policy(**overrides):
    defaults = dict(
        is_enabled=True,
        allowed_email_domains=["acme.com"],
        allowed_sso_providers=["okta-acme"],
        requires_customer_identity_source=True,
    )
    defaults.update(overrides)
    return OrganizationSSOPolicyDTO(**defaults)


class _MarkedConfigQuery:
    """Stands in for OrganizationSSOConfig.objects.filter until the marker field exists."""

    def __init__(self, configs):
        self.configs = list(configs)
        self.filter_kwargs = None
        self.exclude_kwargs = None

    def filter(self, **kwargs):
        self.filter_kwargs = kwargs
        return self

    def exclude(self, **kwargs):
        self.exclude_kwargs = kwargs
        organization_id = kwargs.get("organization_id")
        return [
            config
            for config in self.configs
            if config.organization_id != organization_id
        ]

    def __iter__(self):
        return iter(self.configs)


@override_settings(
    USE_EDA_PERMISSIONS=False,
    CACHES=LOC_MEM_CACHE,
    SSO_INTERNAL_BYPASS_EMAIL_DOMAINS=["weni.ai", "vtex.com"],
)
class NormalizeIdentitySourceTestCase(TestCase):
    def setUp(self):
        cache.clear()

    def test_accepts_and_lowercases_a_valid_identity_source(self):
        self.assertEqual(normalize_identity_source("Okta"), "okta")

    def test_trims_surrounding_whitespace(self):
        self.assertEqual(normalize_identity_source("  okta-acme  "), "okta-acme")

    def test_accepts_hyphenated_identity_source_at_max_length(self):
        value = "a" * 63
        self.assertEqual(normalize_identity_source(value), value)

    def test_rejects_identity_source_longer_than_63_characters(self):
        with self.assertRaises(SSOPolicyValidationError):
            normalize_identity_source("a" * 64)

    def test_rejects_empty_and_whitespace_only_values(self):
        with self.assertRaises(SSOPolicyValidationError):
            normalize_identity_source("")
        with self.assertRaises(SSOPolicyValidationError):
            normalize_identity_source("   ")

    def test_rejects_underscore_dot_and_leading_or_trailing_hyphen(self):
        for value in ("okta_acme", "okta.acme", "-okta", "okta-", "okta--acme"):
            with self.assertRaises(SSOPolicyValidationError):
                normalize_identity_source(value)


@override_settings(
    USE_EDA_PERMISSIONS=False,
    CACHES=LOC_MEM_CACHE,
    SSO_INTERNAL_BYPASS_EMAIL_DOMAINS=["weni.ai", "vtex.com"],
)
class NormalizeEmailDomainTestCase(TestCase):
    def setUp(self):
        cache.clear()

    def test_accepts_and_lowercases_a_bare_domain(self):
        self.assertEqual(normalize_email_domain("Acme.COM"), "acme.com")

    def test_trims_surrounding_whitespace(self):
        self.assertEqual(normalize_email_domain("  acme.com  "), "acme.com")

    def test_rejects_empty_and_whitespace_only_values(self):
        with self.assertRaises(SSOPolicyValidationError):
            normalize_email_domain("")
        with self.assertRaises(SSOPolicyValidationError):
            normalize_email_domain("   ")

    def test_rejects_at_sign(self):
        with self.assertRaises(SSOPolicyValidationError):
            normalize_email_domain("user@acme.com")
        with self.assertRaises(SSOPolicyValidationError):
            normalize_email_domain("@acme.com")

    def test_rejects_internal_whitespace(self):
        with self.assertRaises(SSOPolicyValidationError):
            normalize_email_domain("acme .com")

    def test_rejects_wildcard(self):
        with self.assertRaises(SSOPolicyValidationError):
            normalize_email_domain("*.acme.com")

    def test_rejects_value_without_a_dot(self):
        with self.assertRaises(SSOPolicyValidationError):
            normalize_email_domain("acmecom")


@override_settings(
    USE_EDA_PERMISSIONS=False,
    CACHES=LOC_MEM_CACHE,
    SSO_INTERNAL_BYPASS_EMAIL_DOMAINS=["weni.ai", "vtex.com"],
)
class ValidateOrganizationSSOPolicyUseCaseTestCase(TestCase):
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway):
        mock_get_gateway.return_value = StripeMockGateway()
        cache.clear()
        self.organization = create_organization("SSO Policy Org")
        self.use_case = ValidateOrganizationSSOPolicyUseCase()

    def _execute(self, policy, other_marked_configs=None, organization=None):
        organization = organization or self.organization
        query = _MarkedConfigQuery(
            [] if other_marked_configs is None else other_marked_configs
        )
        with patch.object(
            OrganizationSSOConfig.objects, "filter", side_effect=query.filter
        ):
            result = self.use_case.execute(organization, policy)
        return result, query

    def test_rejects_marker_when_sso_is_not_enabled(self):
        with self.assertRaises(SSOPolicyValidationError):
            self.use_case.execute(
                self.organization, _policy(is_enabled=False)
            )

    def test_rejects_marker_when_provider_list_is_empty(self):
        with self.assertRaises(SSOPolicyValidationError):
            self.use_case.execute(
                self.organization, _policy(allowed_sso_providers=[])
            )

    def test_rejects_marker_when_domain_list_is_empty(self):
        with self.assertRaises(SSOPolicyValidationError):
            self.use_case.execute(
                self.organization, _policy(allowed_email_domains=[])
            )

    def test_accepts_complete_state_and_returns_normalized_dto(self):
        policy = _policy(
            allowed_email_domains=["  ACME.COM  "],
            allowed_sso_providers=["  Okta-Acme  "],
        )
        result, query = self._execute(policy)

        self.assertEqual(
            result,
            OrganizationSSOPolicyDTO(
                is_enabled=True,
                allowed_email_domains=["acme.com"],
                allowed_sso_providers=["okta-acme"],
                requires_customer_identity_source=True,
            ),
        )
        self.assertEqual(
            query.filter_kwargs, {"requires_customer_identity_source": True}
        )
        self.assertEqual(
            query.exclude_kwargs, {"organization_id": self.organization.pk}
        )

    def test_accepts_shared_domain_when_identity_source_sets_are_equal(self):
        holder = create_organization("Holder Org")
        holder_config = OrganizationSSOConfig.objects.create(
            organization=holder,
            is_enabled=True,
            allowed_email_domains=["acme.com"],
            allowed_sso_providers=["okta-b", "okta-a"],
        )
        policy = _policy(allowed_sso_providers=["okta-a", "okta-b"])

        result, query = self._execute(policy, other_marked_configs=[holder_config])

        self.assertEqual(result.allowed_email_domains, ["acme.com"])
        self.assertEqual(
            query.exclude_kwargs, {"organization_id": self.organization.pk}
        )

    def test_rejects_shared_domain_when_identity_source_sets_differ(self):
        holder = create_organization("HolderOrgShouldNeverAppear")
        holder_source = "okta-holder-secret-name"
        holder_config = OrganizationSSOConfig.objects.create(
            organization=holder,
            is_enabled=True,
            allowed_email_domains=["acme.com"],
            allowed_sso_providers=[holder_source],
        )
        policy = _policy(allowed_sso_providers=["okta-acme"])

        with self.assertRaises(SSOPolicyValidationError) as raised:
            self._execute(policy, other_marked_configs=[holder_config])

        message = str(raised.exception)
        self.assertIn("already in use", message)
        self.assertNotIn(holder.name, message)
        self.assertNotIn(holder_source, message)

    def test_set_inequality_is_what_decides_the_domain_conflict(self):
        holder = create_organization("Set Inequality Holder")
        holder_config = OrganizationSSOConfig.objects.create(
            organization=holder,
            is_enabled=True,
            allowed_email_domains=["acme.com"],
            allowed_sso_providers=["okta-acme", "okta-extra"],
        )
        policy = _policy(allowed_sso_providers=["okta-acme"])

        with self.assertRaises(SSOPolicyValidationError):
            self._execute(policy, other_marked_configs=[holder_config])

    def test_revalidating_own_stored_domains_is_accepted(self):
        stored = OrganizationSSOConfig.objects.create(
            organization=self.organization,
            is_enabled=True,
            allowed_email_domains=["acme.com"],
            allowed_sso_providers=["okta-acme"],
        )
        result, query = self._execute(
            _policy(), other_marked_configs=[stored]
        )

        self.assertEqual(result.allowed_email_domains, ["acme.com"])
        self.assertEqual(
            query.filter_kwargs, {"requires_customer_identity_source": True}
        )
        self.assertEqual(
            query.exclude_kwargs, {"organization_id": self.organization.pk}
        )
        self.assertEqual(query.exclude(**query.exclude_kwargs), [])
