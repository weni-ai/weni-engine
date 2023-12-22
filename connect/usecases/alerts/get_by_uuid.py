from django.core.exceptions import ValidationError

from connect.alerts.models import Alert
from .exceptions import AlertNotFound
from .auths import AlertAuthsUseCase


def get_alert_by_uuid(
    uuid: str,
    token: str
) -> Alert:

    auth = AlertAuthsUseCase()
    auth.has_permission(token=token)

    try:
        return Alert.objects.get(uuid=uuid)
    except Alert.DoesNotExist:
        raise AlertNotFound()
    except ValidationError:
        raise ValidationError(message="Invalid UUID")
