from unittest.mock import MagicMock

from django.core.cache import cache
from django.test import TestCase, override_settings

from connect.services.keycloak.service import KeycloakCredentialsService


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "keycloak-credentials-service-tests",
        }
    }
)
class KeycloakCredentialsServiceTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.keycloak_client = MagicMock()
        self.service = KeycloakCredentialsService(keycloak_client=self.keycloak_client)

    def test_returns_and_caches_client_result(self):
        self.keycloak_client.has_password_credential.return_value = True

        self.assertTrue(self.service.has_password_credential("user@weni.ai"))
        self.assertTrue(self.service.has_password_credential("user@weni.ai"))

        self.keycloak_client.has_password_credential.assert_called_once()

    def test_caches_false_results(self):
        self.keycloak_client.has_password_credential.return_value = False

        self.assertFalse(self.service.has_password_credential("user@weni.ai"))
        self.assertFalse(self.service.has_password_credential("user@weni.ai"))

        self.assertEqual(self.keycloak_client.has_password_credential.call_count, 2)

    def test_cache_key_is_case_insensitive(self):
        self.keycloak_client.has_password_credential.return_value = True

        self.service.has_password_credential("User@Weni.ai")
        self.service.has_password_credential("user@weni.ai")

        self.keycloak_client.has_password_credential.assert_called_once()

    def test_returns_none_and_does_not_cache_on_client_failure(self):
        self.keycloak_client.has_password_credential.side_effect = Exception("down")

        self.assertIsNone(self.service.has_password_credential("user@weni.ai"))
        self.assertIsNone(self.service.has_password_credential("user@weni.ai"))

        self.assertEqual(self.keycloak_client.has_password_credential.call_count, 2)

    def test_invalidate_clears_cached_value(self):
        self.keycloak_client.has_password_credential.return_value = True

        self.service.has_password_credential("user@weni.ai")
        self.service.invalidate("user@weni.ai")
        self.service.has_password_credential("user@weni.ai")

        self.assertEqual(self.keycloak_client.has_password_credential.call_count, 2)
