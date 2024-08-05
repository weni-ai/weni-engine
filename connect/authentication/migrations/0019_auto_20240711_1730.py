# Generated by Django 3.2.23 on 2024-07-11 17:30

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("authentication", "0018_user_identity_provider"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="user",
            name="identity_provider",
        ),
        migrations.CreateModel(
            name="UserIdentityProvider",
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
                ("provider", models.CharField(max_length=255)),
                ("provider_user_id", models.CharField(max_length=255)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="identity_provider",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]