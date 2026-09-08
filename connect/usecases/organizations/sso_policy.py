import logging
import re
from dataclasses import dataclass
from typing import List

from connect.common.models import Organization, OrganizationSSOConfig
from connect.usecases.organizations.exceptions import SSOPolicyValidationError

logger = logging.getLogger(__name__)

_IDENTITY_SOURCE_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_MAX_IDENTITY_SOURCE_LENGTH = 63


@dataclass(frozen=True)
class OrganizationSSOPolicyDTO:
    """Resulting organization SSO policy state handed to the shared validator."""

    is_enabled: bool
    allowed_email_domains: List[str]
    allowed_sso_providers: List[str]
    requires_customer_identity_source: bool


def normalize_identity_source(value: str) -> str:
    """Lowercase, trim, then require I1's identity-source shape and length."""
    normalized = value.strip().lower()
    if len(normalized) > _MAX_IDENTITY_SOURCE_LENGTH or not _IDENTITY_SOURCE_PATTERN.match(
        normalized
    ):
        raise SSOPolicyValidationError(f"Invalid identity source: '{value}'")
    return normalized


def normalize_email_domain(value: str) -> str:
    """Lowercase, trim, then require I2's bare-domain shape."""
    normalized = value.strip().lower()
    if (
        not normalized
        or "@" in normalized
        or any(character.isspace() for character in normalized)
        or "*" in normalized
        or "." not in normalized
    ):
        raise SSOPolicyValidationError(f"Invalid email domain: '{value}'")
    return normalized


class ValidateOrganizationSSOPolicyUseCase:
    """Enforce I1–I4 on a resulting policy and return the normalized DTO."""

    def execute(
        self, organization: Organization, policy: OrganizationSSOPolicyDTO
    ) -> OrganizationSSOPolicyDTO:
        logger.info(
            f"Validating SSO policy for organization_id={organization.pk}"
        )
        normalized = OrganizationSSOPolicyDTO(
            is_enabled=policy.is_enabled,
            allowed_email_domains=[
                normalize_email_domain(domain)
                for domain in policy.allowed_email_domains
            ],
            allowed_sso_providers=[
                normalize_identity_source(provider)
                for provider in policy.allowed_sso_providers
            ],
            requires_customer_identity_source=policy.requires_customer_identity_source,
        )
        self._assert_customer_identity_source_is_complete(normalized)
        self._assert_domain_not_claimed_by_another_source(organization, normalized)
        return normalized

    def _assert_customer_identity_source_is_complete(
        self, policy: OrganizationSSOPolicyDTO
    ) -> None:
        if not policy.requires_customer_identity_source:
            return
        if not policy.is_enabled:
            raise SSOPolicyValidationError(
                "Customer identity source requires SSO to be enabled"
            )
        if not policy.allowed_sso_providers:
            raise SSOPolicyValidationError(
                "Customer identity source requires a non-empty provider list"
            )
        if not policy.allowed_email_domains:
            raise SSOPolicyValidationError(
                "Customer identity source requires a non-empty domain list"
            )

    def _assert_domain_not_claimed_by_another_source(
        self, organization: Organization, policy: OrganizationSSOPolicyDTO
    ) -> None:
        if not policy.requires_customer_identity_source:
            return
        our_domains = set(policy.allowed_email_domains)
        our_sources = set(policy.allowed_sso_providers)
        for other in self._other_marked_configs(organization):
            other_domains = {
                normalize_email_domain(domain)
                for domain in other.allowed_email_domains
            }
            overlapping = our_domains.intersection(other_domains)
            if not overlapping:
                continue
            other_sources = {
                normalize_identity_source(provider)
                for provider in other.allowed_sso_providers
            }
            if other_sources != our_sources:
                domain = sorted(overlapping)[0]
                raise SSOPolicyValidationError(
                    f"The domain '{domain}' is already in use"
                )

    def _other_marked_configs(self, organization: Organization):
        return OrganizationSSOConfig.objects.filter(
            requires_customer_identity_source=True
        ).exclude(organization_id=organization.pk)
