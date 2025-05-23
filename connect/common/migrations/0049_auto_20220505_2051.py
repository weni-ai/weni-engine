# Generated by Django 3.2.13 on 2022-05-05 20:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0048_merge_20220502_2037"),
    ]

    operations = [
        migrations.AlterField(
            model_name="requestrocketpermission",
            name="role",
            field=models.PositiveIntegerField(
                choices=[
                    (0, "not set"),
                    (1, "user"),
                    (2, "admin"),
                    (3, "agent"),
                    (4, "service manager"),
                ],
                default=0,
                verbose_name="role",
            ),
        ),
        migrations.AlterField(
            model_name="rocketauthorization",
            name="role",
            field=models.PositiveIntegerField(
                choices=[
                    (0, "not set"),
                    (1, "user"),
                    (2, "admin"),
                    (3, "agent"),
                    (4, "service manager"),
                ],
                default=0,
                verbose_name="role",
            ),
        ),
    ]
