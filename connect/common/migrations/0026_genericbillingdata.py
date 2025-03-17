# Generated by Django 3.2.9 on 2021-11-29 18:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0025_billingplan_is_active"),
    ]

    operations = [
        migrations.CreateModel(
            name="GenericBillingData",
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
                    "_free_active_contacts_limit",
                    models.PositiveIntegerField(
                        default=200, verbose_name="Free active contacts limit"
                    ),
                ),
            ],
        ),
    ]
