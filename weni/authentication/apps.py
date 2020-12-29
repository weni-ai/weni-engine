from django.apps import AppConfig


class AuthenticationConfig(AppConfig):
    name = "weni.authentication"

    def ready(self):
        from .signals import update_user_keycloak  # noqa: F401
