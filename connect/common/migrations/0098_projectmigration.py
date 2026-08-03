import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("common", "0097_organizationssoconfig"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProjectMigration",
            fields=[
                (
                    "uuid",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        verbose_name="UUID",
                    ),
                ),
                (
                    "org_from",
                    models.UUIDField(verbose_name="source organization UUID"),
                ),
                (
                    "org_to",
                    models.UUIDField(verbose_name="destination organization UUID"),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "pending"),
                            ("PUBLISH_FAILED", "publish failed"),
                            ("IN_PROGRESS", "in progress"),
                            ("PARTIAL_ERROR", "partial error"),
                            ("COMPLETED", "completed"),
                        ],
                        default="PENDING",
                        max_length=20,
                        verbose_name="status",
                    ),
                ),
                (
                    "modules_status",
                    models.JSONField(
                        blank=True, default=dict, verbose_name="modules status"
                    ),
                ),
                (
                    "requested_by",
                    models.CharField(
                        blank=True,
                        max_length=255,
                        null=True,
                        verbose_name="requested by",
                    ),
                ),
                (
                    "published_at",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="published at"
                    ),
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
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="migrations",
                        to="common.project",
                    ),
                ),
            ],
            options={
                "verbose_name": "project migration",
                "verbose_name_plural": "project migrations",
            },
        ),
        migrations.AddIndex(
            model_name="projectmigration",
            index=models.Index(
                fields=["project", "status"],
                name="projectmigration_proj_status",
            ),
        ),
    ]
