# Generated by Django 3.2.16 on 2023-03-30 15:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0072_auto_20230123_1728'),
    ]

    operations = [
        migrations.AlterField(
            model_name='project',
            name='template_type',
            field=models.CharField(blank=True, choices=[('support', 'support'), ('lead_capture', 'lead capture'), ('omie_lead_capture', 'omie_lead_capture'), ('omie_financial', 'omie_financial'), ('omie_financial+chatgpt', 'omie_financial+chatgpt')], help_text='Project template type', max_length=30, null=True, verbose_name='Template type'),
        ),
        migrations.AlterField(
            model_name='recentactivity',
            name='action',
            field=models.CharField(choices=[('ADD', 'Add'), ('UPDATE', 'Entity updated'), ('CREATE', 'Entity Created')], max_length=15),
        ),
    ]
