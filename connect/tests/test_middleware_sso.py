from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings

from connect.api.v1.tests.utils import create_user_and_token
from connect.middleware import WeniOIDCAuthentication
from connect.services.keycloak.service import KeycloakCredentialsService


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "middleware-sso-tests",
        }
    }
)
class WeniOIDCAuthenticationPasswordCacheTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()
        self.user, self.token = create_user_and_token("oidc_sso_user")
        self.keycloak_client = MagicMock()
        self.keycloak_client.has_password_credential.return_value = True
        self.credentials_service = KeycloakCredentialsService(
            keycloak_client=self.keycloak_client
        )

    @patch.object(WeniOIDCAuthentication, "verify_login")
    @patch("connect.middleware.jwt.decode")
    @patch("mozilla_django_oidc.contrib.drf.OIDCAuthentication.authenticate")
    def test_authenticate_invalidates_password_cache(
        self, mock_super_authenticate, mock_jwt_decode, _mock_verify_login
    ):
        mock_super_authenticate.return_value = (self.user, "access-token")
        mock_jwt_decode.return_value = {"identity_provider": "google"}

        self.credentials_service.has_password_credential(self.user.email)
        self.keycloak_client.has_password_credential.assert_called_once()

        request = self.factory.get("/")
        with patch(
            "connect.middleware.KeycloakCredentialsService",
            return_value=self.credentials_service,
        ):
            WeniOIDCAuthentication().authenticate(request)

        self.credentials_service.has_password_credential(self.user.email)
        self.assertEqual(self.keycloak_client.has_password_credential.call_count, 2)
