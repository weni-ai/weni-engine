from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0098_projectmigration"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="currency",
            field=models.CharField(
                blank=True,
                max_length=3,
                null=True,
                verbose_name="Project currency",
            ),
        ),
    ]
