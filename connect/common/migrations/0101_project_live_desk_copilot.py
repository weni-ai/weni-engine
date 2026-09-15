from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("common", "0100_organizationssoconfig_requires_customer_identity_source"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="is_live_desk_copilot",
            field=models.BooleanField(
                default=False, verbose_name="Is live desk copilot"
            ),
        ),
        migrations.AddField(
            model_name="project",
            name="parent_project",
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    "Source of truth for VTEX account lookups when this project "
                    "is a live desk copilot."
                ),
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="copilot_projects",
                to="common.project",
                verbose_name="Parent project",
            ),
        ),
        migrations.AddConstraint(
            model_name="project",
            constraint=models.CheckConstraint(
                check=(
                    models.Q(
                        ("is_live_desk_copilot", False),
                        ("parent_project__isnull", True),
                    )
                    | models.Q(
                        ("is_live_desk_copilot", True),
                        ("parent_project__isnull", False),
                    )
                ),
                name="common_project_copilot_requires_parent",
            ),
        ),
    ]
