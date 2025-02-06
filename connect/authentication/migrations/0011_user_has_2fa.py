# Generated by Django 3.2.13 on 2022-06-03 19:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0010_alter_user_language"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="has_2fa",
            field=models.BooleanField(
                default=False, verbose_name="Two factor authentication"
            ),
        ),
    ]
