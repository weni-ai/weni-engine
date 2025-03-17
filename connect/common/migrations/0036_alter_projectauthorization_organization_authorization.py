# Generated by Django 3.2.11 on 2022-02-03 20:06

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0035_projectauthorization"),
    ]

    operations = [
        migrations.AlterField(
            model_name="projectauthorization",
            name="organization_authorization",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to="common.organizationauthorization",
            ),
        ),
    ]
