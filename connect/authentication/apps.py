from django.apps import AppConfig


class AuthenticationConfig(AppConfig):
    name = "connect.authentication"

    def ready(self):
        from .signals import signal_user  # noqa: F401
