from .auths import AlertAuthsUseCase
from .get_by_uuid import get_alert_by_uuid
from connect.alerts.models import Alert


def delete_alert(
    alert_uuid: str,
    token: str,
) -> Alert:

    AlertAuthsUseCase().has_permission(token=token)

    alert = get_alert_by_uuid(
        uuid=alert_uuid,
        token=token
    )
    alert.delete()

    return alert
