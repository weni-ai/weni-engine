from django.apps import AppConfig


class CommonConfig(AppConfig):
    name = "connect.common"

    def ready(self):
        from .signals import create_service_status  # noqa: F401
        from .signals import create_service_default_in_all_user  # noqa: F401
        from .signals import org_authorizations  # noqa: F401
