# Generated by Django 3.2.23 on 2024-11-29 15:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0088_rename_type_project_project_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="vtex_account",
            field=models.CharField(
                blank=True, max_length=100, null=True, verbose_name="VTEX account"
            ),
        ),
    ]
