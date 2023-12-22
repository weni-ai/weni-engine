from .auths import AlertAuthsUseCase
from connect.alerts.models import Alert


def create_alert(
    can_be_closed: bool,
    text: str,
    type: int,
    token: str,
) -> Alert:

    AlertAuthsUseCase().has_permission(token=token)

    return Alert.objects.create(
        can_be_closed=can_be_closed,
        text=text,
        type=type
    )
