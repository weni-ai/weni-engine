from django.conf import settings
from keycloak import KeycloakAdmin
import requests
import json


class KeycloakControl:  # pragma: no cover
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

    def configure_2fa(self, email: str, active: bool):
        """
        Configure two factor authentication to user
        """
        user_id = self.get_user_id_by_email(email)
        if user_id is not None:
            if active:
                response = self.instance.update_user(
                    user_id=user_id,
                    payload={'requiredActions': ['CONFIGURE_TOTP']}
                )
                return response
            else:
                # remove required action
                response = self.instance.update_user(
                    user_id=user_id,
                    payload={'requiredActions': []}
                )
                # remove otp credential
                credentials = self.get_credentials(email)
                credential_id = next((credential["id"] for credential in credentials if credential["type"] == "otp"), None)
                if credential_id:
                    self.remove_credential(user_id, credential_id)
                return response
        else:
            return 'User not found'

    def get_credentials(self, email):
        # using requests until we update python-keycloak version
        token = self.instance._token["access_token"]
        realm_name = settings.OIDC_RP_REALM_NAME
        server_url = settings.OIDC_RP_SERVER_URL
        user_id = self.get_user_id_by_email(email)

        headers = {"Authorization": f"Bearer {token}"}

        r = requests.get(f"{server_url}admin/realms/{realm_name}/users/{user_id}/credentials", headers=headers)
        return json.loads(r.text)

    def remove_credential(self, user_id, credential_id):
        token = self.instance._token["access_token"]
        realm_name = settings.OIDC_RP_REALM_NAME
        server_url = settings.OIDC_RP_SERVER_URL

        headers = {"Authorization": f"Bearer {token}"}

        r = requests.delete(f"{server_url}admin/realms/{realm_name}/users/{user_id}/credentials/{credential_id}", headers=headers)

        return r.status_code
