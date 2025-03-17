# Generated by Django 3.2.20 on 2023-08-24 19:06

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("template_projects", "0005_templatetype_base_project_uuid"),
        ("common", "0079_auto_20230523_1821"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="project_template_type",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="template_projects",
                to="template_projects.templatetype",
            ),
        )
    ]
