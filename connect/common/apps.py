from django.apps import AppConfig


class CommonConfig(AppConfig):
    name = "connect.common"

    def ready(self):
        from .signals import create_service_status  # noqa: F401
        from .signals import create_service_default_in_all_user  # noqa: F401
        from .signals import (  # noqa: F401
            invalidate_plan_status_on_billing_delete,
            invalidate_plan_status_on_billing_save,
            invalidate_plan_status_on_organization_save,
            invalidate_plan_status_on_project_delete,
        )
