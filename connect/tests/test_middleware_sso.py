from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings
from rest_framework.exceptions import AuthenticationFailed

from connect.api.v1.tests.utils import create_user_and_token
from connect.middleware import WeniAuthentication, WeniOIDCAuthentication
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


@override_settings(JWT_PUBLIC_KEY="")
class WeniAuthenticationTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user, _ = create_user_and_token("connect_weni_auth_user")
        self.oidc_authentication = MagicMock()

    def _request(self):
        request = self.factory.get("/", HTTP_AUTHORIZATION="Bearer keycloak-token")
        request.headers = {"Authorization": "Bearer keycloak-token"}
        return request

    def _authentication(self, **kwargs):
        return WeniAuthentication(
            oidc_authentication=self.oidc_authentication, **kwargs
        )

    def test_keycloak_branch_delegates_to_connect_oidc_wrapper(self):
        request = self._request()

        def authenticate(target_request):
            target_request.session_identity_provider = "google"
            return self.user, "keycloak-token"

        self.oidc_authentication.authenticate.side_effect = authenticate
        self.oidc_authentication.backend.verify_token.return_value = {
            "email": self.user.email,
            "project_uuid": "project-from-claims",
        }

        user, auth_context = self._authentication().authenticate(request)

        self.assertEqual(user, self.user)
        self.assertTrue(auth_context.is_keycloak)
        self.assertEqual(auth_context.project_uuid, "project-from-claims")
        self.assertEqual(request.session_identity_provider, "google")

    def test_keycloak_branch_rejects_token_the_wrapper_cannot_read(self):
        self.oidc_authentication.authenticate.return_value = None

        with self.assertRaises(AuthenticationFailed):
            self._authentication().authenticate(self._request())

    def test_injected_oidc_backend_keeps_the_library_flow(self):
        backend = MagicMock()
        backend.get_or_create_user.return_value = self.user
        backend.verify_token.return_value = {"email": self.user.email}

        user, auth_context = self._authentication(oidc_backend=backend).authenticate(
            self._request()
        )

        self.assertEqual(user, self.user)
        self.assertTrue(auth_context.is_keycloak)
        self.oidc_authentication.authenticate.assert_not_called()
