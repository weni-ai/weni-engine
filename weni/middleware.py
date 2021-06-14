import logging

from django.conf import settings
from django.utils import translation
from mozilla_django_oidc.auth import OIDCAuthenticationBackend
from mozilla_django_oidc.contrib.drf import OIDCAuthentication

from weni.celery import app as celery_app

LOGGER = logging.getLogger("weni_django_oidc")


class WeniOIDCAuthenticationBackend(OIDCAuthenticationBackend):
    """
    Custom authentication class for django-admin.
    """

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
        username = self.get_username(claims)
        user = self.UserModel.objects.create_user(email, username)

        old_username = user.username
        user.username = claims.get("preferred_username", old_username)
        user.first_name = claims.get("given_name", "")
        user.last_name = claims.get("family_name", "")
        user.email = claims.get("email", "")
        user.save()

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

        return instance
