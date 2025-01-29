# Generated by Django 3.2.18 on 2023-05-23 18:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0078_merge_20230511_2229"),
    ]

    operations = [
        migrations.AlterField(
            model_name="project",
            name="template_type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("support", "support"),
                    ("lead_capture", "lead capture"),
                    ("lead_capture+chatgpt", "lead_capture+chatgpt"),
                    ("omie_lead_capture", "omie_lead_capture"),
                    ("omie_financial", "omie_financial"),
                    ("omie_financial+chatgpt", "omie_financial+chatgpt"),
                    ("sac+chatgpt", "sac+chatgpt"),
                ],
                help_text="Project template type",
                max_length=30,
                null=True,
                verbose_name="Template type",
            ),
        ),
        migrations.AlterField(
            model_name="recentactivity",
            name="action",
            field=models.CharField(
                choices=[
                    ("CREATE", "Entity Created"),
                    ("TRAIN", "Entity Trained"),
                    ("INTEGRATE", "Entity integrated"),
                    ("ADD", "Add"),
                    ("UPDATE", "Entity updated"),
                ],
                max_length=15,
            ),
        ),
    ]
