# Generated by Django 3.2.13 on 2022-08-12 20:06

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0057_auto_20220620_2002"),
    ]

    operations = [
        migrations.CreateModel(
            name="TemplateProject",
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
                ("wa_demo_token", models.CharField(max_length=30)),
                (
                    "classifier_uuid",
                    models.UUIDField(default=uuid.uuid4, verbose_name="UUID"),
                ),
                ("first_access", models.BooleanField(default=True)),
                (
                    "flow_uuid",
                    models.UUIDField(default=uuid.uuid4, verbose_name="UUID"),
                ),
                (
                    "authorization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="common.projectauthorization",
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="template_project",
                        to="common.project",
                    ),
                ),
            ],
        ),
    ]
