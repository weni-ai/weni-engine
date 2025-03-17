# Generated by Django 3.2.16 on 2022-11-30 01:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0066_auto_20221025_1811"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoice",
            name="invoice_amount",
            field=models.DecimalField(decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AlterField(
            model_name="billingplan",
            name="plan",
            field=models.CharField(
                choices=[
                    ("free", "free"),
                    ("trial", "trial"),
                    ("start", "start"),
                    ("scale", "scale"),
                    ("advanced", "advanced"),
                    ("enterprise", "enterprise"),
                    ("custom", "custom"),
                ],
                max_length=10,
                verbose_name="plan",
            ),
        ),
    ]
