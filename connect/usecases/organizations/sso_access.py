import logging
from typing import Dict, Optional

from django.db.models import QuerySet

from connect.common.models import Organization, OrganizationSSOConfig
from connect.services.keycloak.service import KeycloakCredentialsService

logger = logging.getLogger(__name__)

PROVIDER_GOOGLE = OrganizationSSOConfig.PROVIDER_GOOGLE
PROVIDER_MICROSOFT = OrganizationSSOConfig.PROVIDER_MICROSOFT

BROKER_ALIAS_TO_PROVIDER = {
    "google": PROVIDER_GOOGLE,
    "microsoft": PROVIDER_MICROSOFT,
    "azure-ad": PROVIDER_MICROSOFT,
    "azuread": PROVIDER_MICROSOFT,
    "entra-id": PROVIDER_MICROSOFT,
    "office365": PROVIDER_MICROSOFT,
}


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
        self._password_blocked_by_email: Dict[str, bool] = {}

    def execute(
        self, organization: Organization, user, session_identity_provider: Optional[str]
    ) -> bool:
        config = getattr(organization, "sso_config", None)
        if config is None or not config.is_enabled:
            return True

        provider = resolve_sso_provider(session_identity_provider)
        if not config.is_provider_allowed(provider):
            return False

        if not config.is_email_domain_allowed(user.email):
            return False

        return not self._is_password_blocked(user.email)

    def _is_password_blocked(self, email: str) -> bool:
        """An unknown credential state (Keycloak unreachable) fails closed:
        enforcing organizations stay hidden rather than leaking access."""
        if email not in self._password_blocked_by_email:
            has_password = self.credentials_service.has_password_credential(email)
            self._password_blocked_by_email[email] = has_password is not False
        return self._password_blocked_by_email[email]


class FilterAccessibleOrganizationsUseCase:
    """Removes SSO-enforcing organizations the current session does not
    comply with from an organization queryset (used by list endpoints so
    non-compliant organizations are never even shown to the user)."""

    def __init__(
        self, evaluate_usecase: Optional[EvaluateOrganizationSSOAccessUseCase] = None
    ):
        self.evaluate_usecase = (
            evaluate_usecase or EvaluateOrganizationSSOAccessUseCase()
        )

    def execute(
        self, queryset: QuerySet, user, session_identity_provider: Optional[str]
    ) -> QuerySet:
        enforcing = queryset.filter(sso_config__is_enabled=True).select_related(
            "sso_config"
        )
        blocked_pks = [
            organization.pk
            for organization in enforcing
            if not self.evaluate_usecase.execute(
                organization, user, session_identity_provider
            )
        ]
        if blocked_pks:
            return queryset.exclude(pk__in=blocked_pks)
        return queryset
