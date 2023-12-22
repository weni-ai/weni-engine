from .auths import AlertAuthsUseCase
from .get_by_uuid import get_alert_by_uuid
from connect.alerts.models import Alert


class AlertUpdateUseCase:

    def update_alert(
        self,
        alert_id: int,
        token: str,
        can_be_closed: bool = None,
        text: str = None,
        type: int = None,
    ) -> Alert:

        AlertAuthsUseCase().has_permission(token=token)

        alert = get_alert_by_uuid(
            uuid=alert_id,
            token=token
        )

        if can_be_closed is not None:
            alert.can_be_closed = can_be_closed

        if text is not None:
            alert.text = text

        if type is not None:
            alert.type = type

        alert.save()

        return alert
