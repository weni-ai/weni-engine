# Generated by Django 3.2.12 on 2022-04-20 14:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0002_alter_syncmanagertask_finished_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='syncmanagertask',
            name='retried',
            field=models.BooleanField(default=False, help_text='Whether this task retry or not.'),
        ),
    ]
