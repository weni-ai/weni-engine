import json
import logging

from django.conf import settings
from django.utils import translation
from django_redis import get_redis_connection
from mozilla_django_oidc.auth import OIDCAuthenticationBackend
from mozilla_django_oidc.contrib.drf import OIDCAuthentication
from rest_framework import HTTP_HEADER_ENCODING, exceptions
from rest_framework.authentication import BaseAuthentication, get_authorization_header

from connect.celery import app as celery_app

from connect.utils import check_module_permission

from connect.authentication.models import User

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
        user.set_identity_providers()

        if locale:
            if locale.lower() == "pt-br":
                language = settings.LANGUAGES[1][0]
            elif locale.lower() == "es":
                language = settings.LANGUAGES[2][0]
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
        user.set_identity_providers()
        user.save()

        check_module_permission(claims, user)

        return user


class WeniOIDCAuthentication(OIDCAuthentication):
    def authenticate(self, request):
        instance = super().authenticate(request=request)

        if instance is None:
            return instance

        if not instance[0] or instance[0].is_anonymous:
            return instance

        user_language = getattr(instance[0], "language", None)
        if not user_language:
            return instance

        translation.activate(user_language)

        user = instance[0]

        if user.first_login and not user.first_login_token:
            user.save_first_login_token(instance[1])

        WeniOIDCAuthentication.verify_login(user, instance[1])

        return instance

    @staticmethod
    def verify_login(user: User, request_token: str):
        """Compares the first login token with the token sent in the request to check if is the same session"""

        user_token = user.first_login_token

        if user.first_login and user_token != request_token:
            user.set_verify_email()


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
