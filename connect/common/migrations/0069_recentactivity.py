# Generated by Django 3.2.16 on 2022-12-22 19:02

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("common", "0068_auto_20221207_2027"),
    ]

    operations = [
        migrations.CreateModel(
            name="RecentActivity",
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
                    "action",
                    models.CharField(
                        choices=[
                            ("ADD", "Add"),
                            ("UPDATE", "Entity updated"),
                            ("CREATE", "Entity Created"),
                        ],
                        max_length=15,
                    ),
                ),
                (
                    "entity",
                    models.CharField(
                        choices=[
                            ("USER", "User Entity"),
                            ("FLOW", "Flow Entity"),
                            ("CHANNEL", "Channel Entity"),
                            ("TRIGGER", "Trigger Entity"),
                            ("CAMPAIGN", "Campaign Entity"),
                        ],
                        max_length=20,
                    ),
                ),
                ("entity_name", models.CharField(max_length=255, null=True)),
                (
                    "created_on",
                    models.DateTimeField(auto_now_add=True, verbose_name="created on"),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="project_recent_activity",
                        to="common.project",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="user_recent_activy",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]
