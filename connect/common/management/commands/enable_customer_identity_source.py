from django.core.management.base import BaseCommand, CommandError

from connect.usecases.organizations.enable_customer_identity_source import (
    EnableCustomerIdentitySourceDTO,
    EnableCustomerIdentitySourceUseCase,
)
from connect.usecases.organizations.exceptions import (
    OrganizationDoesNotExist,
    SSOPolicyValidationError,
)


class Command(BaseCommand):
    help = (
        "Enable, update, or disable a customer identity source binding "
        "for an organization."
    )

    def add_arguments(self, parser):
        parser.add_argument("--organization", required=True)
        parser.add_argument("--identity-source", action="append", default=None)
        parser.add_argument("--email-domain", action="append", default=None)
        parser.add_argument("--disable", action="store_true")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        dto = EnableCustomerIdentitySourceDTO(
            organization_uuid=options["organization"],
            allowed_sso_providers=options["identity_source"] or [],
            allowed_email_domains=options["email_domain"] or [],
            disable=options["disable"],
            dry_run=options["dry_run"],
        )
        try:
            result = EnableCustomerIdentitySourceUseCase().execute(dto)
        except OrganizationDoesNotExist as exc:
            raise CommandError(str(exc)) from exc
        except SSOPolicyValidationError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(f"organization: {result.organization_uuid}")
        self.stdout.write(
            f"requires_customer_identity_source: {result.requires_customer_identity_source}"
        )
        self.stdout.write(f"is_enabled: {result.is_enabled}")
        self.stdout.write(f"allowed_sso_providers: {result.allowed_sso_providers}")
        self.stdout.write(f"allowed_email_domains: {result.allowed_email_domains}")
        if result.dry_run:
            self.stdout.write("not persisted")
        elif result.unchanged:
            self.stdout.write("unchanged")
