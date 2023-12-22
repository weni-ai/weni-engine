from connect.alerts.models import Alert
from .auths import AlertAuthsUseCase


def list_alerts(
    token: str,
) -> Alert:

    AlertAuthsUseCase().has_permission(token=token)

    alerts = Alert.objects.all()

    return alerts
