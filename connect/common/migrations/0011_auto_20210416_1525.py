# Generated by Django 2.2.19 on 2021-04-16 15:25

from django.db import migrations, models
import django.db.models.deletion


def noop(apps, schema_editor):  # pragma: no cover
    pass


def delete_newsletter(apps, schema_editor):  # pragma: no cover
    Newsletter = apps.get_model("common", "Newsletter")
    Newsletter.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0010_auto_20210415_1331"),
    ]

    operations = [
        migrations.RunPython(delete_newsletter, noop),
        migrations.CreateModel(
            name="NewsletterLanguage",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "language",
                    models.CharField(
                        choices=[("en-us", "English"), ("pt-br", "Portuguese")],
                        default="en-us",
                        max_length=10,
                        verbose_name="language",
                    ),
                ),
                ("title", models.CharField(max_length=50, verbose_name="title")),
                ("description", models.TextField(verbose_name="description")),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="created at"),
                ),
            ],
            options={
                "verbose_name": "dashboard newsletter",
            },
        ),
        migrations.RemoveField(
            model_name="newsletter",
            name="description",
        ),
        migrations.RemoveField(
            model_name="newsletter",
            name="title",
        ),
        migrations.AddField(
            model_name="newsletter",
            name="newsletter_language",
            field=models.ForeignKey(
                default=None,
                on_delete=django.db.models.deletion.CASCADE,
                to="common.NewsletterLanguage",
            ),
            preserve_default=False,
        ),
    ]
