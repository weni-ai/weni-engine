from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings
from rest_framework.exceptions import AuthenticationFailed

from connect.api.v1.tests.utils import create_user_and_token
from connect.authentication.models import User
from connect.common.mocks import StripeMockGateway
from connect.common.models import OrganizationAuthorization, OrganizationSSOConfig
from connect.middleware import (
    WeniAuthentication,
    WeniOIDCAuthentication,
    WeniOIDCAuthenticationBackend,
)
from connect.services.keycloak.service import KeycloakCredentialsService
from connect.usecases.organizations.tests.test_sso_access import create_organization


@override_settings(
    USE_EDA_PERMISSIONS=False,
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "middleware-sso-tests",
        }
    },
    SSO_INTERNAL_BYPASS_EMAIL_DOMAINS=["weni.ai", "vtex.com"],
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

    @patch.object(WeniOIDCAuthentication, "verify_login")
    @patch("connect.middleware.jwt.decode")
    @patch("mozilla_django_oidc.contrib.drf.OIDCAuthentication.authenticate")
    def test_okta_customer_identity_provider_lands_unmodified(
        self, mock_super_authenticate, mock_jwt_decode, _mock_verify_login
    ):
        mock_super_authenticate.return_value = (self.user, "access-token")
        mock_jwt_decode.return_value = {"identity_provider": "okta-acme"}

        request = self.factory.get("/")
        with patch(
            "connect.middleware.KeycloakCredentialsService",
            return_value=self.credentials_service,
        ):
            WeniOIDCAuthentication().authenticate(request)

        self.assertEqual(request.session_identity_provider, "okta-acme")


@override_settings(
    USE_EDA_PERMISSIONS=False,
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "middleware-sso-create-user-tests",
        }
    },
    SSO_INTERNAL_BYPASS_EMAIL_DOMAINS=["weni.ai", "vtex.com"],
    SYNC_ORGANIZATION_INTELIGENCE=False,
)
class WeniOIDCAuthenticationBackendCreateUserTestCase(TestCase):
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway):
        mock_get_gateway.return_value = StripeMockGateway()
        cache.clear()
        self.organization = create_organization("Mapped Domain Customer Org")
        OrganizationSSOConfig.objects.create(
            organization=self.organization,
            is_enabled=True,
            allowed_sso_providers=["okta-acme"],
            allowed_email_domains=["acme.com"],
            requires_customer_identity_source=True,
        )

    def test_first_authentication_on_mapped_domain_creates_user_without_authorization(
        self,
    ):
        claims = {
            "email": "maria@acme.com",
            "preferred_username": "maria.acme",
            "given_name": "Maria",
            "family_name": "Acme",
        }

        user = WeniOIDCAuthenticationBackend().create_user(claims)

        self.assertEqual(user.email, "maria@acme.com")
        self.assertTrue(User.objects.filter(email="maria@acme.com").exists())
        self.assertFalse(
            OrganizationAuthorization.objects.filter(
                user=user, organization=self.organization
            ).exists()
        )
        self.assertFalse(
            OrganizationAuthorization.objects.filter(
                organization=self.organization
            ).exists()
        )


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
