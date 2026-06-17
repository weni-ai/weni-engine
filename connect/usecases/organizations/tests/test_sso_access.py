import uuid
from unittest.mock import patch

from django.test import TestCase, override_settings

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
    BuildOrganizationSSOAccessMapUseCase,
    EvaluateOrganizationSSOAccessUseCase,
    ExcludeNonCompliantOrganizationProjectsUseCase,
    OrganizationSSOAccessDisabledReason,
    enrich_serializer_context_with_sso_access,
    resolve_sso_provider,
)

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

    def test_memoizes_credential_lookup_per_email(self):
        self.create_sso_config(is_enabled=True)
        credentials_service = FakeCredentialsService(has_password=False)
        usecase = EvaluateOrganizationSSOAccessUseCase(
            credentials_service=credentials_service
        )

        usecase.execute(self.organization, self.user, "google")
        usecase.execute(self.organization, self.user, "google")

        self.assertEqual(len(credentials_service.calls), 1)


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
