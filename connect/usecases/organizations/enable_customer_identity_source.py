import logging
from dataclasses import dataclass
from typing import List, Optional

from django.db import transaction

from connect.common.models import Organization, OrganizationSSOConfig
from connect.services.keycloak.service import KeycloakCredentialsService
from connect.usecases.organizations.retrieve import RetrieveOrganizationUseCase
from connect.usecases.organizations.sso_policy import (
    OrganizationSSOPolicyDTO,
    ValidateOrganizationSSOPolicyUseCase,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EnableCustomerIdentitySourceDTO:
    organization_uuid: str
    allowed_sso_providers: List[str]
    allowed_email_domains: List[str]
    disable: bool = False
    dry_run: bool = False


@dataclass(frozen=True)
class EnableCustomerIdentitySourceResult:
    organization_uuid: str
    is_enabled: bool
    requires_customer_identity_source: bool
    allowed_sso_providers: List[str]
    allowed_email_domains: List[str]
    persisted: bool
    unchanged: bool
    dry_run: bool


class EnableCustomerIdentitySourceUseCase:
    def __init__(
        self, credentials_service: Optional[KeycloakCredentialsService] = None
    ):
        self.credentials_service = credentials_service or KeycloakCredentialsService()

    def execute(
        self, dto: EnableCustomerIdentitySourceDTO
    ) -> EnableCustomerIdentitySourceResult:
        with transaction.atomic():
            organization = RetrieveOrganizationUseCase().get_organization_by_uuid(
                dto.organization_uuid
            )
            sso_config, _ = OrganizationSSOConfig.objects.get_or_create(
                organization=organization
            )
            logger.info(
                f"Resolving customer identity source for organization {organization.uuid}"
            )
            normalized = self._validated_resulting_policy(organization, sso_config, dto)
            if dto.dry_run:
                return self._return_without_persisting(
                    organization, normalized, unchanged=False, dry_run=True
                )
            if self._stored_policy_matches(sso_config, normalized):
                logger.info(
                    f"Customer identity source unchanged for organization {organization.uuid}"
                )
                return self._result(
                    organization,
                    normalized,
                    persisted=False,
                    unchanged=True,
                    dry_run=False,
                )
            self._persist(sso_config, normalized)
            logger.info(
                f"Customer identity source persisted for organization {organization.uuid}"
            )
            return self._result(
                organization,
                normalized,
                persisted=True,
                unchanged=False,
                dry_run=False,
            )

    def _validated_resulting_policy(
        self,
        organization: Organization,
        sso_config: OrganizationSSOConfig,
        dto: EnableCustomerIdentitySourceDTO,
    ) -> OrganizationSSOPolicyDTO:
        return ValidateOrganizationSSOPolicyUseCase().execute(
            organization, self._build_resulting_policy(sso_config, dto)
        )

    def _build_resulting_policy(
        self, sso_config: OrganizationSSOConfig, dto: EnableCustomerIdentitySourceDTO
    ) -> OrganizationSSOPolicyDTO:
        if dto.disable:
            return OrganizationSSOPolicyDTO(
                is_enabled=False,
                allowed_email_domains=list(sso_config.allowed_email_domains),
                allowed_sso_providers=list(sso_config.allowed_sso_providers),
                requires_customer_identity_source=False,
            )
        return OrganizationSSOPolicyDTO(
            is_enabled=True,
            allowed_email_domains=list(dto.allowed_email_domains),
            allowed_sso_providers=list(dto.allowed_sso_providers),
            requires_customer_identity_source=True,
        )

    def _stored_policy_matches(
        self, sso_config: OrganizationSSOConfig, normalized: OrganizationSSOPolicyDTO
    ) -> bool:
        return (
            sso_config.is_enabled == normalized.is_enabled
            and sso_config.requires_customer_identity_source
            == normalized.requires_customer_identity_source
            and list(sso_config.allowed_email_domains)
            == list(normalized.allowed_email_domains)
            and list(sso_config.allowed_sso_providers)
            == list(normalized.allowed_sso_providers)
        )

    def _persist(
        self, sso_config: OrganizationSSOConfig, normalized: OrganizationSSOPolicyDTO
    ) -> None:
        sso_config.is_enabled = normalized.is_enabled
        sso_config.requires_customer_identity_source = (
            normalized.requires_customer_identity_source
        )
        sso_config.allowed_email_domains = list(normalized.allowed_email_domains)
        sso_config.allowed_sso_providers = list(normalized.allowed_sso_providers)
        sso_config.save()

    def _return_without_persisting(
        self,
        organization: Organization,
        normalized: OrganizationSSOPolicyDTO,
        unchanged: bool,
        dry_run: bool,
    ) -> EnableCustomerIdentitySourceResult:
        transaction.set_rollback(True)
        logger.info(
            f"Customer identity source dry-run for organization {organization.uuid}"
        )
        return self._result(
            organization,
            normalized,
            persisted=False,
            unchanged=unchanged,
            dry_run=dry_run,
        )

    def _result(
        self,
        organization: Organization,
        normalized: OrganizationSSOPolicyDTO,
        persisted: bool,
        unchanged: bool,
        dry_run: bool,
    ) -> EnableCustomerIdentitySourceResult:
        return EnableCustomerIdentitySourceResult(
            organization_uuid=str(organization.uuid),
            is_enabled=normalized.is_enabled,
            requires_customer_identity_source=(
                normalized.requires_customer_identity_source
            ),
            allowed_sso_providers=list(normalized.allowed_sso_providers),
            allowed_email_domains=list(normalized.allowed_email_domains),
            persisted=persisted,
            unchanged=unchanged,
            dry_run=dry_run,
        )
