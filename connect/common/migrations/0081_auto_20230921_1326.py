# Generated by Django 3.2.20 on 2023-09-21 13:26

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0080_auto_20230824_1906'),
    ]

    operations = [
        migrations.AlterField(
            model_name='project',
            name='template_type',
            field=models.CharField(blank=True, choices=[('support', 'support'), ('lead_capture', 'lead capture'), ('lead_capture+chatgpt', 'lead_capture+chatgpt'), ('omie_lead_capture', 'omie_lead_capture'), ('omie_financial', 'omie_financial'), ('omie_financial+chatgpt', 'omie_financial+chatgpt'), ('sac+chatgpt', 'sac+chatgpt')], help_text='Project template type', max_length=255, null=True, verbose_name='Template type'),
        ),
        migrations.AlterField(
            model_name='recentactivity',
            name='action',
            field=models.CharField(choices=[('INTEGRATE', 'Entity integrated'), ('TRAIN', 'Entity Trained'), ('UPDATE', 'Entity updated'), ('ADD', 'Add'), ('CREATE', 'Entity Created')], max_length=15),
        ),
        migrations.AlterField(
            model_name='templateproject',
            name='classifier_uuid',
            field=models.UUIDField(default=uuid.uuid4, null=True, verbose_name='UUID'),
        ),
        migrations.AlterField(
            model_name='templateproject',
            name='flow_uuid',
            field=models.UUIDField(default=uuid.uuid4, null=True, verbose_name='UUID'),
        ),
    ]