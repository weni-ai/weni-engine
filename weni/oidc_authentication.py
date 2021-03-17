import logging

from mozilla_django_oidc.auth import OIDCAuthenticationBackend

from weni import utils
from weni.common.models import Organization

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

        grpc_instance = utils.get_grpc_types().get("inteligence")

        organizations = grpc_instance.list_organizations(user_email=user.email)

        for organization in organizations:
            org, created = Organization.objects.get_or_create(
                inteligence_organization=organization.get("id"),
                defaults={"name": organization.get("name"), "description": ""},
            )

            role = grpc_instance.get_user_organization_permission_role(
                user_email=user.email, organization_id=organization.get("id")
            )

            org.authorizations.create(user=user, role=role)

        return user

    def update_user(self, user, claims):
        user.name = claims.get("name", "")
        user.email = claims.get("email", "")
        user.save()

        return user
