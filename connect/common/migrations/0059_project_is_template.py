# Generated by Django 3.2.13 on 2022-08-15 18:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0058_templateproject"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="is_template",
            field=models.BooleanField(default=False),
        ),
    ]
