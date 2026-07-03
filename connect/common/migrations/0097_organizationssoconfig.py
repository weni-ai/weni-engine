# Generated for SSO-enforced organizations feature

import uuid

import django.db.models.deletion
from django.db import migrations, models


def backfill_sso_config(apps, schema_editor):
    Organization = apps.get_model("common", "Organization")
    OrganizationSSOConfig = apps.get_model("common", "OrganizationSSOConfig")

    for organization in Organization.objects.filter(
        require_external_provider_for_access=True
    ):
        OrganizationSSOConfig.objects.get_or_create(
            organization=organization,
            defaults={"is_enabled": True},
        )


def remove_sso_config(apps, schema_editor):
    OrganizationSSOConfig = apps.get_model("common", "OrganizationSSOConfig")
    OrganizationSSOConfig.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("common", "0096_auto_20260514_1736"),
    ]

    operations = [
        migrations.CreateModel(
            name="OrganizationSSOConfig",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "uuid",
                    models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
                ),
                (
                    "is_enabled",
                    models.BooleanField(
                        default=False,
                        help_text=(
                            "When enabled, members can only access this "
                            "organization through an allowed SSO provider and "
                            "without a password configured in Keycloak."
                        ),
                        verbose_name="SSO-only access enabled",
                    ),
                ),
                (
                    "allowed_email_domains",
                    models.JSONField(blank=True, default=list),
                ),
                (
                    "allowed_sso_providers",
                    models.JSONField(blank=True, default=list),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="created at"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="updated at"),
                ),
                (
                    "organization",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sso_config",
                        to="common.organization",
                    ),
                ),
            ],
            options={
                "verbose_name": "organization SSO configuration",
                "verbose_name_plural": "organization SSO configurations",
            },
        ),
        migrations.RunPython(backfill_sso_config, remove_sso_config),
    ]
