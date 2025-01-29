# Generated by Django 3.2.11 on 2022-02-08 11:57

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0039_rocketauthorization"),
    ]

    operations = [
        migrations.AddField(
            model_name="projectauthorization",
            name="rocket_authorization",
            field=models.ForeignKey(
                default=None,
                on_delete=django.db.models.deletion.CASCADE,
                to="common.rocketauthorization",
            ),
        ),
        migrations.AlterField(
            model_name="projectauthorization",
            name="role",
            field=models.PositiveIntegerField(
                choices=[
                    (0, "not set"),
                    (3, "viewer"),
                    (2, "contributor"),
                    (1, "moderator"),
                ],
                default=0,
                verbose_name="role",
            ),
        ),
        migrations.AlterField(
            model_name="requestpermissionproject",
            name="role",
            field=models.PositiveIntegerField(
                choices=[
                    (0, "not set"),
                    (3, "viewer"),
                    (2, "contributor"),
                    (1, "moderator"),
                ],
                default=0,
                verbose_name="role",
            ),
        ),
    ]
