# Generated by Django 3.2.11 on 2022-03-23 12:52

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("common", "0044_auto_20220303_2024"),
    ]

    operations = [
        migrations.CreateModel(
            name="RequestRocketPermission",
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
                ("email", models.EmailField(max_length=254, verbose_name="email")),
                (
                    "role",
                    models.PositiveIntegerField(
                        choices=[(0, "not set"), (1, "agent"), (2, "service manager")],
                        default=0,
                        verbose_name="role",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="common.project"
                    ),
                ),
            ],
        ),
    ]
