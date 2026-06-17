import logging
from typing import Optional

from django.conf import settings
from django.core.cache import cache

from connect.api.v1.keycloak import KeycloakControl

logger = logging.getLogger(__name__)


class KeycloakCredentialsService:
    """Reads Keycloak credential state with a cache in front of the admin API.

    ``has_password_credential`` returns ``None`` when the credential state
    could not be determined (Keycloak unreachable), so callers can decide how
    to handle the unknown case instead of silently assuming a value.
    """

    CACHE_KEY_PREFIX = "sso:has_password"

    def __init__(self, keycloak_client: Optional[KeycloakControl] = None):
        self._keycloak_client = keycloak_client

    @property
    def keycloak_client(self) -> KeycloakControl:
        if self._keycloak_client is None:
            self._keycloak_client = KeycloakControl()
        return self._keycloak_client

    @classmethod
    def _cache_key(cls, email: str) -> str:
        return f"{cls.CACHE_KEY_PREFIX}:{email.lower()}"

    def has_password_credential(self, email: str) -> Optional[bool]:
        cache_key = self._cache_key(email)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            has_password = self.keycloak_client.has_password_credential(email)
        except Exception as error:
            logger.error(f"Failed to read Keycloak credentials for {email}: {error}")
            return None

        if has_password:
            cache.set(cache_key, True, settings.SSO_PASSWORD_CACHE_TTL)
        return has_password

    def invalidate(self, email: str) -> None:
        cache.delete(self._cache_key(email))
