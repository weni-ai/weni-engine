from connect.alerts.models import Alert
from .auths import AlertAuthsUseCase


class AlertListUseCase:
    def list_alerts(
        self,
        token: str,
    ) -> Alert:

        AlertAuthsUseCase().has_permission(token=token)

        alerts = Alert.objects.all()

        return alerts
