# Generated by Django 3.2.20 on 2023-10-05 19:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0081_auto_20230921_1326"),
    ]

    operations = [
        migrations.AddField(
            model_name="billingplan",
            name="plan_method",
            field=models.CharField(
                choices=[
                    ("attendances", "attendances"),
                    ("active_contacts", "active_contacts"),
                ],
                default="attendances",
                max_length=15,
                verbose_name="plan_method",
            ),
        ),
        migrations.AlterField(
            model_name="recentactivity",
            name="action",
            field=models.CharField(
                choices=[
                    ("ADD", "Add"),
                    ("CREATE", "Entity Created"),
                    ("UPDATE", "Entity updated"),
                    ("TRAIN", "Entity Trained"),
                    ("INTEGRATE", "Entity integrated"),
                ],
                max_length=15,
            ),
        ),
    ]
