# Generated by Django 3.2.13 on 2022-06-20 20:02

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0056_auto_20220620_1718"),
    ]

    operations = [
        migrations.AlterField(
            model_name="organizationauthorization",
            name="role",
            field=models.PositiveIntegerField(
                choices=[
                    (0, "not set"),
                    (2, "contributor"),
                    (3, "admin"),
                    (1, "viewer"),
                    (4, "financial"),
                    (5, "support"),
                ],
                default=0,
                verbose_name="role",
            ),
        ),
        migrations.AlterField(
            model_name="requestpermissionorganization",
            name="role",
            field=models.PositiveIntegerField(
                choices=[
                    (0, "not set"),
                    (2, "contributor"),
                    (3, "admin"),
                    (1, "viewer"),
                    (4, "financial"),
                    (5, "support"),
                ],
                default=0,
                verbose_name="role",
            ),
        ),
    ]
