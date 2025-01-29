# Generated by Django 3.2.13 on 2022-05-05 21:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0049_auto_20220505_2051"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="flow_id",
            field=models.PositiveIntegerField(
                null=True, unique=True, verbose_name="flow identification ID"
            ),
        ),
    ]
