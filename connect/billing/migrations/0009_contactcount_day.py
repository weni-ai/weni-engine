# Generated by Django 3.2.15 on 2022-09-26 21:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0008_auto_20220808_2133'),
    ]

    operations = [
        migrations.AddField(
            model_name='contactcount',
            name='day',
            field=models.DateTimeField(null=True),
        ),
    ]
