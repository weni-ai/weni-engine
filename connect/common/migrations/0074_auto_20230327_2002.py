# Generated by Django 3.2.16 on 2023-03-27 20:02

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0073_alter_recentactivity_action"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProxyOrg",
            fields=[],
            options={
                "verbose_name": "Organization Authorization",
                "verbose_name_plural": "Organization Authorization",
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=("common.organization",),
        ),
        migrations.AlterField(
            model_name="recentactivity",
            name="action",
            field=models.CharField(
                choices=[
                    ("UPDATE", "Entity updated"),
                    ("ADD", "Add"),
                    ("CREATE", "Entity Created"),
                    ("INTEGRATE", "Entity integrated"),
                    ("TRAIN", "Entity Trained"),
                ],
                max_length=15,
            ),
        ),
        migrations.CreateModel(
            name="NewsletterOrganization",
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
                ("title", models.CharField(max_length=50, verbose_name="title")),
                ("description", models.TextField(verbose_name="description")),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="created at"),
                ),
                (
                    "newsletter",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="common.newsletter",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="org_newsletter",
                        to="common.organization",
                    ),
                ),
            ],
        ),
    ]
