# Generated by Django 2.2.19 on 2021-05-12 20:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0018_requestpermissionorganization"),
    ]

    operations = [
        migrations.AlterField(
            model_name="requestpermissionorganization",
            name="email",
            field=models.EmailField(max_length=254, verbose_name="email"),
        ),
    ]
