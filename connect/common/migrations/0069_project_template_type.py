# Generated by Django 3.2.16 on 2022-12-22 17:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0068_auto_20221207_2027"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="template_type",
            field=models.CharField(
                blank=True,
                choices=[("support", "support"), ("lead_capture", "lead capture")],
                help_text="Project template type",
                max_length=20,
                null=True,
                verbose_name="Template type",
            ),
        ),
    ]
