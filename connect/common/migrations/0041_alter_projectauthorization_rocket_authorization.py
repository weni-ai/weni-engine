# Generated by Django 3.2.11 on 2022-02-08 12:43

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0040_auto_20220208_1157'),
    ]

    operations = [
        migrations.AlterField(
            model_name='projectauthorization',
            name='rocket_authorization',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='common.rocketauthorization'),
        ),
    ]
