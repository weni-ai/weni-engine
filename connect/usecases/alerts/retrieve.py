from .get_by_uuid import get_alert_by_uuid
from .auths import AlertAuthsUseCase
from connect.alerts.models import Alert


def retrieve_alert(
    alert_uuid: int,
    token: str,
) -> Alert:

    AlertAuthsUseCase().has_permission(token=token)

    alert = get_alert_by_uuid(
        uuid=alert_uuid,
        token=token
    )

    return alert
