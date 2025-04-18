# Generated by Django 3.2.16 on 2023-01-04 14:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0072_auto_20221229_2215"),
    ]

    operations = [
        migrations.AlterField(
            model_name="recentactivity",
            name="action",
            field=models.CharField(
                choices=[
                    ("CREATE", "Entity Created"),
                    ("INTEGRATE", "Entity integrated"),
                    ("UPDATE", "Entity updated"),
                    ("TRAIN", "Entity Trained"),
                    ("ADD", "Add"),
                ],
                max_length=15,
            ),
        ),
    ]
