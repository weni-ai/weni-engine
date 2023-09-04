# Generated by Django 3.2.20 on 2023-08-23 18:57

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0079_auto_20230523_1821'),
    ]

    operations = [
        migrations.AddField(
            model_name='organization',
            name='allowed_ips',
            field=django.contrib.postgres.fields.ArrayField(base_field=models.CharField(blank=True, max_length=255), blank=True, help_text='list of IPs from where the user can access the org', null=True, size=None),
        ),
        migrations.AlterField(
            model_name='recentactivity',
            name='action',
            field=models.CharField(choices=[('UPDATE', 'Entity updated'), ('ADD', 'Add'), ('CREATE', 'Entity Created'), ('INTEGRATE', 'Entity integrated'), ('TRAIN', 'Entity Trained')], max_length=15),
        ),
    ]
