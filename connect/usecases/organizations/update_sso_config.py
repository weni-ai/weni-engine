import logging
from dataclasses import dataclass
from typing import List, Optional

from connect.common.models import Organization, OrganizationSSOConfig
from connect.services.keycloak.service import KeycloakCredentialsService
from connect.usecases.organizations.exceptions import SSOConfigLockoutError
from connect.usecases.organizations.sso_access import (
    is_sso_internal_bypass_email,
    resolve_sso_provider,
)
from connect.usecases.organizations.sso_policy import (
    OrganizationSSOPolicyDTO,
    ValidateOrganizationSSOPolicyUseCase,
)

logger = logging.getLogger(__name__)


@dataclass
class UpdateOrganizationSSOConfigDTO:
    is_enabled: Optional[bool] = None
    allowed_email_domains: Optional[List[str]] = None
    allowed_sso_providers: Optional[List[str]] = None


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
        resulting = OrganizationSSOPolicyDTO(
            is_enabled=(
                sso_config.is_enabled if dto.is_enabled is None else dto.is_enabled
            ),
            allowed_email_domains=(
                sso_config.allowed_email_domains
                if dto.allowed_email_domains is None
                else dto.allowed_email_domains
            ),
            allowed_sso_providers=(
                sso_config.allowed_sso_providers
                if dto.allowed_sso_providers is None
                else dto.allowed_sso_providers
            ),
            requires_customer_identity_source=(
                sso_config.requires_customer_identity_source
            ),
        )
        normalized = ValidateOrganizationSSOPolicyUseCase().execute(
            organization, resulting
        )

        sso_config.is_enabled = normalized.is_enabled
        sso_config.allowed_email_domains = normalized.allowed_email_domains
        sso_config.allowed_sso_providers = normalized.allowed_sso_providers

        if sso_config.is_enabled:
            self._validate_actor_not_locked_out(
                sso_config, actor, session_identity_provider
            )

        sso_config.save()
        logger.info(
            f"SSO config updated for organization {organization.uuid} "
            f"by {actor.email}: enabled={sso_config.is_enabled}"
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
        if is_sso_internal_bypass_email(actor.email):
            return

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
        has_password = self.credentials_service.has_password_credential(actor.email)
        if has_password is True:
            raise SSOConfigLockoutError("Your account still has a password configured")
        if has_password is None:
            raise SSOConfigLockoutError(
                "Your password state could not be verified; try again later"
            )
