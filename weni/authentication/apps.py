from django.apps import AppConfig


class AuthenticationConfig(AppConfig):
    name = "weni.authentication"

    def ready(self):
        from .signals import signal_user  # noqa: F401
