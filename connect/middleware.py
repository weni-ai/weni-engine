import json
import logging
import jwt

from django.conf import settings
from django.utils import translation
from django_redis import get_redis_connection
from mozilla_django_oidc.auth import OIDCAuthenticationBackend
from mozilla_django_oidc.contrib.drf import OIDCAuthentication
from rest_framework import HTTP_HEADER_ENCODING, exceptions
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from weni_commons.auth import WeniAuthentication as BaseWeniAuthentication

from connect.celery import app as celery_app

from connect.utils import check_module_permission

from connect.authentication.models import User
from connect.services.keycloak.service import KeycloakCredentialsService

LOGGER = logging.getLogger("weni_django_oidc")


class WeniOIDCAuthenticationBackend(OIDCAuthenticationBackend):
    """
    Custom authentication class for django-admin.
    """

    cache_token = settings.OIDC_CACHE_TOKEN
    cache_ttl = settings.OIDC_CACHE_TTL

    def get_userinfo(self, access_token, *args):
        if not self.cache_token:
            return super().get_userinfo(access_token, *args)

        redis_connection = get_redis_connection()

        userinfo = redis_connection.get(access_token)

        if userinfo is not None:
            return json.loads(userinfo)

        userinfo = super().get_userinfo(access_token, *args)
        redis_connection.set(access_token, json.dumps(userinfo), self.cache_ttl)

        return userinfo

    def verify_claims(self, claims):
        # validação de permissão
        verified = super(WeniOIDCAuthenticationBackend, self).verify_claims(claims)
        # is_admin = "admin" in claims.get("roles", [])
        return verified  # and is_admin # not checking for user roles from keycloak at this time

    def get_username(self, claims):
        username = claims.get("preferred_username")
        if username:
            return username
        return super(WeniOIDCAuthenticationBackend, self).get_username(claims=claims)

    def create_user(self, claims):
        # Override existing create_user method in OIDCAuthenticationBackend
        email = claims.get("email")
        locale = claims.get("locale")

        username = self.get_username(claims)
        user = self.UserModel.objects.create_user(email, username)

        old_username = user.username
        user.username = claims.get("preferred_username", old_username)
        user.first_name = claims.get("given_name", "")
        user.last_name = claims.get("family_name", "")
        user.email = claims.get("email", "")
        user.first_login = True

        if locale:
            if locale.lower() == "pt-br":
                language = settings.LANGUAGES[1][0]
            elif locale.lower() == "es":
                language = settings.LANGUAGES[2][0]
            elif locale.lower() == "ro":
                language = settings.LANGUAGES[3][0]
            else:
                language = settings.LANGUAGES[0][0]

            user.language = language

        user.save()
        check_module_permission(claims, user)

        if settings.SYNC_ORGANIZATION_INTELIGENCE:
            task = celery_app.send_task(  # pragma: no cover
                name="migrate_organization",
                args=[str(user.email)],
            )
            task.wait()  # pragma: no cover

        return user

    def update_user(self, user, claims):
        user.name = claims.get("name", "")
        user.email = claims.get("email", "")
        user.save()

        check_module_permission(claims, user)

        return user


class WeniOIDCAuthentication(OIDCAuthentication):
    def authenticate(self, request):
        instance = super().authenticate(request=request)
        if instance is None:
            return instance
        identity_provider = jwt.decode(
            instance[1], options={"verify_signature": False}
        ).get("identity_provider")

        # Expose the current session's SSO provider so SSO-access enforcement
        # reads the live claim instead of the append-only provider history.
        request.session_identity_provider = identity_provider

        if not instance[0] or instance[0].is_anonymous:
            return instance

        user_language = getattr(instance[0], "language", None)
        if not user_language:
            return instance

        translation.activate(user_language)

        user = instance[0]
        KeycloakCredentialsService().invalidate(user.email)

        if user.first_login and not user.first_login_token:
            user.save_first_login_token(instance[1])

        if identity_provider:
            user.set_identity_providers(identity_provider=identity_provider)

        WeniOIDCAuthentication.verify_login(user, instance[1])

        return instance

    @staticmethod
    def verify_login(user: User, request_token: str):
        """Compares the first login token with the token sent in the request to check if is the same session"""

        user_token = user.first_login_token

        if user.first_login and user_token != request_token:
            user.set_verify_email()


class WeniAuthentication(BaseWeniAuthentication):
    """The shared Weni authentication, wired to Connect's Keycloak session setup.

    Every Connect route that adopts the shared authentication uses this class,
    so the JWT flow stays exactly the library's while Keycloak callers keep the
    per-session work ``WeniOIDCAuthentication`` does — most importantly exposing
    ``session_identity_provider``, the live claim SSO enforcement relies on,
    plus language activation and first-login verification. Keycloak tokens must
    therefore arrive in ``Authorization: Bearer``, the only header that wrapper
    reads.

    The private hook is overridden deliberately: weni-commons has no public
    extension point for the Keycloak branch yet.
    """

    def __init__(self, oidc_backend=None, oidc_authentication=None):
        """Initialize the authenticator.

        Args:
            oidc_backend: Optional OIDC backend. When given, the library's own
                Keycloak flow is used, skipping Connect's session setup.
            oidc_authentication: Optional Connect OIDC wrapper, injected by
                tests; built lazily otherwise so the JWT flow never depends on
                the OIDC configuration.
        """
        super().__init__(oidc_backend=oidc_backend)
        self._oidc_authentication = oidc_authentication

    def _authenticate_with_keycloak(self, request, token):
        if self._oidc_backend is not None:
            return super()._authenticate_with_keycloak(request, token)

        oidc_authentication = self._get_oidc_authentication()
        instance = oidc_authentication.authenticate(request)
        if instance is None:
            raise exceptions.AuthenticationFailed("Invalid token.")

        user = instance[0]
        claims = self._extract_keycloak_claims(token, oidc_authentication.backend, user)
        return user, self._build_keycloak_auth_context(request, user, claims)

    def _get_oidc_authentication(self):
        if self._oidc_authentication is None:
            self._oidc_authentication = WeniOIDCAuthentication()
        return self._oidc_authentication


class ExternalAuthentication(BaseAuthentication):
    """
    Provide OpenID authentication for DRF.
    """

    def authenticate(self, request):
        """
        Authenticate the request and return a tuple of (user, token) or None
        if there was no authentication attempt.
        """
        access_token = self.get_access_token(request)

        return None, access_token

    def get_access_token(self, request):
        """
        Get the access token based on a request.

        Returns None if no authentication details were provided. Raises
        AuthenticationFailed if the token is incorrect.
        """
        header = get_authorization_header(request)

        if not header:
            return None
        header = header.decode(HTTP_HEADER_ENCODING)

        auth = header.split()

        if auth[0].lower() != "externalauth":
            return None

        if len(auth) == 1:
            msg = 'Invalid "ExternalAuth" header: No credentials provided.'
            raise exceptions.AuthenticationFailed(msg)
        elif len(auth) > 2:
            msg = 'Invalid "ExternalAuth" header: Credentials string should not contain spaces.'
            raise exceptions.AuthenticationFailed(msg)

        if not auth[1] == settings.TOKEN_EXTERNAL_AUTHENTICATION:
            msg = "This Token is not valid"
            raise exceptions.AuthenticationFailed(msg)

        return auth[1]

    def authenticate_header(self, request):
        """
        If this method returns None, a generic HTTP 403 forbidden response is
        returned by DRF when authentication fails.

        By making the method return a string, a 401 is returned instead. The
        return value will be used as the WWW-Authenticate header.
        """
        return "ExternalAuth"
