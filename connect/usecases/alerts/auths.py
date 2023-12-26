from django.conf import settings

from .exceptions import AlertsPermissionDenied


class AlertAuthsUseCase:

    def __init__(self) -> None:
        self.valid_tokens = [
            settings.VERIFICATION_MARKETING_TOKEN,
        ]

    def is_valid(
            self,
            token: str
    ) -> bool:
        return token in self.valid_tokens

    def has_permission(
        self,
        token: str,
    ) -> bool:

        permission_check = self.is_valid(token=token)
        if not permission_check:
            raise AlertsPermissionDenied()

        return self.is_valid(token=token)
