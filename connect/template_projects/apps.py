from django.apps import AppConfig


class TemplateProjectsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'connect.template_projects'

    def ready(self):
        from connect.template_projects.signals import create_template_type  # noqa: F401
