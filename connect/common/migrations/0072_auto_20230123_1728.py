# Generated by Django 3.2.16 on 2023-01-23 17:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0071_merge_20221227_2109'),
    ]

    operations = [
        migrations.AlterField(
            model_name='organization',
            name='inteligence_organization',
            field=models.IntegerField(blank=True, null=True, verbose_name='inteligence organization id'),
        ),
        migrations.AlterField(
            model_name='recentactivity',
            name='action',
            field=models.CharField(choices=[('CREATE', 'Entity Created'), ('ADD', 'Add'), ('UPDATE', 'Entity updated')], max_length=15),
        ),
    ]
