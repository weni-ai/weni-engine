import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional

from django.db.models import QuerySet

from connect.common.models import Organization, OrganizationSSOConfig
from connect.services.keycloak.service import KeycloakCredentialsService

logger = logging.getLogger(__name__)

PROVIDER_GOOGLE = OrganizationSSOConfig.PROVIDER_GOOGLE
PROVIDER_MICROSOFT = OrganizationSSOConfig.PROVIDER_MICROSOFT

ACCESS_STATUS_ACTIVE = "active"
ACCESS_STATUS_DISABLED = "disabled"

BROKER_ALIAS_TO_PROVIDER = {
    "google": PROVIDER_GOOGLE,
    "microsoft": PROVIDER_MICROSOFT,
    "azure-ad": PROVIDER_MICROSOFT,
    "azuread": PROVIDER_MICROSOFT,
    "entra-id": PROVIDER_MICROSOFT,
    "office365": PROVIDER_MICROSOFT,
}


class OrganizationSSOAccessDisabledReason(str, Enum):
    SSO_SESSION_REQUIRED = "sso_session_required"
    SSO_PROVIDER_NOT_ALLOWED = "sso_provider_not_allowed"
    SSO_EMAIL_DOMAIN_NOT_ALLOWED = "sso_email_domain_not_allowed"
    SSO_PASSWORD_CONFIGURED = "sso_password_configured"
    SSO_CREDENTIAL_UNAVAILABLE = "sso_credential_unavailable"


@dataclass(frozen=True)
class OrganizationSSOAccessResult:
    is_compliant: bool
    disabled_reason: Optional[str] = None

    @classmethod
    def compliant(cls) -> "OrganizationSSOAccessResult":
        return cls(is_compliant=True)

    @classmethod
    def non_compliant(
        cls, reason: OrganizationSSOAccessDisabledReason
    ) -> "OrganizationSSOAccessResult":
        return cls(is_compliant=False, disabled_reason=reason.value)


def resolve_sso_provider(broker_alias: str) -> Optional[str]:
    """Map a Keycloak identity-provider broker alias to a canonical provider.

    Unknown aliases are returned lowercased so future providers still surface a
    stable value; a missing alias (non-SSO session) resolves to ``None``.
    """
    if not broker_alias:
        return None
    alias = broker_alias.lower()
    return BROKER_ALIAS_TO_PROVIDER.get(alias, alias)


class EvaluateOrganizationSSOAccessUseCase:
    """Decides whether a user's current session may access an organization.

    A user complies with an SSO-enforcing organization when the current
    session is brokered through an allowed SSO provider, the user's email
    domain is allowed, and the user has no password configured in Keycloak.
    Organizations without an enabled policy always comply, which keeps the
    rule isolated per organization in a multi-tenant setup.
    """

    def __init__(
        self, credentials_service: Optional[KeycloakCredentialsService] = None
    ):
        self.credentials_service = credentials_service or KeycloakCredentialsService()
        self._password_blocked_by_email: Dict[str, Optional[bool]] = {}

    def execute(
        self, organization: Organization, user, session_identity_provider: Optional[str]
    ) -> bool:
        return self.evaluate(organization, user, session_identity_provider).is_compliant

    def evaluate(
        self, organization: Organization, user, session_identity_provider: Optional[str]
    ) -> OrganizationSSOAccessResult:
        config = getattr(organization, "sso_config", None)
        if config is None or not config.is_enabled:
            return OrganizationSSOAccessResult.compliant()

        provider = resolve_sso_provider(session_identity_provider)
        if not provider:
            return OrganizationSSOAccessResult.non_compliant(
                OrganizationSSOAccessDisabledReason.SSO_SESSION_REQUIRED
            )
        if not config.is_provider_allowed(provider):
            return OrganizationSSOAccessResult.non_compliant(
                OrganizationSSOAccessDisabledReason.SSO_PROVIDER_NOT_ALLOWED
            )
        if not config.is_email_domain_allowed(user.email):
            return OrganizationSSOAccessResult.non_compliant(
                OrganizationSSOAccessDisabledReason.SSO_EMAIL_DOMAIN_NOT_ALLOWED
            )

        password_block_reason = self._get_password_block_reason(user.email)
        if password_block_reason:
            return OrganizationSSOAccessResult.non_compliant(password_block_reason)

        return OrganizationSSOAccessResult.compliant()

    def _get_password_block_reason(
        self, email: str
    ) -> Optional[OrganizationSSOAccessDisabledReason]:
        if email not in self._password_blocked_by_email:
            has_password = self.credentials_service.has_password_credential(email)
            if has_password is False:
                self._password_blocked_by_email[email] = False
            elif has_password is True:
                self._password_blocked_by_email[email] = True
            else:
                self._password_blocked_by_email[email] = None

        blocked_state = self._password_blocked_by_email[email]
        if blocked_state is False:
            return None
        if blocked_state is True:
            return OrganizationSSOAccessDisabledReason.SSO_PASSWORD_CONFIGURED
        return OrganizationSSOAccessDisabledReason.SSO_CREDENTIAL_UNAVAILABLE


class ExcludeNonCompliantOrganizationProjectsUseCase:
    """Remove projects belonging to SSO-enforcing orgs the session cannot access."""

    def __init__(
        self, evaluate_usecase: Optional[EvaluateOrganizationSSOAccessUseCase] = None
    ):
        self.evaluate_usecase = (
            evaluate_usecase or EvaluateOrganizationSSOAccessUseCase()
        )

    def execute(
        self, queryset: QuerySet, user, session_identity_provider: Optional[str]
    ) -> QuerySet:
        organization_pks = queryset.values_list("organization_id", flat=True).distinct()
        if not organization_pks:
            return queryset

        enforcing_orgs = Organization.objects.filter(
            pk__in=organization_pks,
            sso_config__is_enabled=True,
        ).select_related("sso_config")

        blocked_pks = [
            organization.pk
            for organization in enforcing_orgs
            if not self.evaluate_usecase.execute(
                organization, user, session_identity_provider
            )
        ]
        if not blocked_pks:
            return queryset

        logger.info(
            f"Excluding projects from non-compliant SSO orgs for user={user.email}: "
            f"org_pks={blocked_pks}"
        )
        return queryset.exclude(organization_id__in=blocked_pks)


class BuildOrganizationSSOAccessMapUseCase:
    """Evaluates SSO access for enforcing organizations in a queryset."""

    def __init__(
        self, evaluate_usecase: Optional[EvaluateOrganizationSSOAccessUseCase] = None
    ):
        self.evaluate_usecase = (
            evaluate_usecase or EvaluateOrganizationSSOAccessUseCase()
        )

    def execute(
        self, queryset: QuerySet, user, session_identity_provider: Optional[str]
    ) -> Dict[int, OrganizationSSOAccessResult]:
        enforcing = queryset.filter(sso_config__is_enabled=True).select_related(
            "sso_config"
        )
        return {
            organization.pk: self.evaluate_usecase.evaluate(
                organization, user, session_identity_provider
            )
            for organization in enforcing
        }


def enrich_serializer_context_with_sso_access(view, context: dict) -> dict:
    if getattr(view, "action", None) not in ("list", "retrieve"):
        return context

    if view.action == "retrieve":
        organization_uuid = view.kwargs.get("uuid")
        queryset = (
            Organization.objects.filter(uuid=organization_uuid)
            if organization_uuid
            else view.get_queryset()
        )
    else:
        queryset = view.get_queryset()

    context["sso_access_results"] = BuildOrganizationSSOAccessMapUseCase().execute(
        queryset,
        view.request.user,
        getattr(view.request, "session_identity_provider", None),
    )
    return context
