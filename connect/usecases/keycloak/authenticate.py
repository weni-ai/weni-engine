from keycloak import KeycloakOpenID
from django.conf import settings
from keycloak.exceptions import KeycloakAuthenticationError


class KeycloakAuthenticateUseCase:
    def __init__(self):
        self.keycloak_client = KeycloakOpenID(
            server_url=settings.OIDC_RP_SERVER_URL,
            client_id=settings.OIDC_RP_CLIENT_ID,
            realm_name=settings.OIDC_RP_REALM_NAME,
            client_secret_key=settings.OIDC_RP_CLIENT_SECRET,
        )

    def execute(self, username: str, password: str) -> dict:
        try:
            token = self.keycloak_client.token(username, password)
            return {
                "access_token": token["access_token"],
                "refresh_token": token["refresh_token"],
                "expires_in": token["expires_in"],
            }
        except KeycloakAuthenticationError:
            raise ValueError("Invalid username or password")
        except Exception as e:
            raise Exception(f"Authentication failed: {str(e)}")
