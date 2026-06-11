import logging
from dataclasses import dataclass, field
from typing import List, Optional

from connect.common.models import Organization, OrganizationSSOConfig
from connect.services.keycloak.service import KeycloakCredentialsService
from connect.usecases.organizations.exceptions import SSOConfigLockoutError
from connect.usecases.organizations.sso_access import resolve_sso_provider

logger = logging.getLogger(__name__)


@dataclass
class UpdateOrganizationSSOConfigDTO:
    is_enabled: bool
    allowed_email_domains: List[str] = field(default_factory=list)
    allowed_sso_providers: List[str] = field(default_factory=list)


class UpdateOrganizationSSOConfigUseCase:
    def __init__(
        self, credentials_service: Optional[KeycloakCredentialsService] = None
    ):
        self.credentials_service = credentials_service or KeycloakCredentialsService()

    def execute(
        self,
        organization: Organization,
        dto: UpdateOrganizationSSOConfigDTO,
        actor,
        session_identity_provider: Optional[str],
    ) -> OrganizationSSOConfig:
        sso_config, _ = OrganizationSSOConfig.objects.get_or_create(
            organization=organization
        )
        sso_config.is_enabled = dto.is_enabled
        sso_config.allowed_email_domains = dto.allowed_email_domains
        sso_config.allowed_sso_providers = dto.allowed_sso_providers

        if dto.is_enabled:
            self._validate_actor_not_locked_out(
                sso_config, actor, session_identity_provider
            )

        sso_config.save()
        logger.info(
            f"SSO config updated for organization {organization.uuid} "
            f"by {actor.email}: enabled={dto.is_enabled}"
        )
        return sso_config

    def _validate_actor_not_locked_out(
        self,
        sso_config: OrganizationSSOConfig,
        actor,
        session_identity_provider: Optional[str],
    ) -> None:
        """Enabling a policy the actor does not comply with would instantly
        hide the organization from the actor themselves."""
        provider = resolve_sso_provider(session_identity_provider)
        if not provider:
            raise SSOConfigLockoutError(
                "Your current session is not authenticated through SSO"
            )
        if not sso_config.is_provider_allowed(provider):
            raise SSOConfigLockoutError(
                "Your current SSO provider is not in the allowed providers"
            )
        if not sso_config.is_email_domain_allowed(actor.email):
            raise SSOConfigLockoutError(
                "Your email domain is not in the allowed domains"
            )
        if self.credentials_service.has_password_credential(actor.email):
            raise SSOConfigLockoutError("Your account still has a password configured")
