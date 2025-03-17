# Generated by Django 3.2.9 on 2021-12-20 17:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0031_billingplan_contract_on"),
    ]

    operations = [
        migrations.AlterField(
            model_name="billingplan",
            name="plan",
            field=models.CharField(
                choices=[
                    ("free", "free"),
                    ("enterprise", "enterprise"),
                    ("custom", "custom"),
                ],
                max_length=10,
                verbose_name="plan",
            ),
        ),
    ]
