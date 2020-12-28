from django.conf import settings
from keycloak import KeycloakAdmin


class KeycloakControl:
    def __init__(self):
        self.instance = self.get_instance()

    def get_instance(self) -> KeycloakAdmin:
        return KeycloakAdmin(
            server_url=settings.OIDC_RP_SERVER_URL,
            realm_name=settings.OIDC_RP_REALM_NAME,
            client_id=settings.OIDC_RP_CLIENT_ID,
            client_secret_key=settings.OIDC_RP_CLIENT_SECRET,
            verify=True,
            auto_refresh_token=["get", "post", "put", "delete"],
        )

    def get_user_id_by_email(self, email: str) -> str:
        """
        Get internal keycloak user id from email
        This is required for further actions against this user.

        UserRepresentation
        https://www.keycloak.org/docs-api/8.0/rest-api/index.html#_userrepresentation

        :param email: id in UserRepresentation

        :return: user_id
        """

        users = self.instance.get_users(query={"email": email})
        return next((user["id"] for user in users if user["email"] == email), None)
