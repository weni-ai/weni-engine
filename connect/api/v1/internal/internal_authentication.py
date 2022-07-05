import requests
from django.conf import settings


class InternalAuthentication:
    # TODO: make this method private
    def get_module_token(self):
        request = requests.post(
            url=settings.OIDC_OP_TOKEN_ENDPOINT,
            data={
                "client_id": settings.OIDC_RP_CLIENT_ID,
                "client_secret": settings.OIDC_RP_CLIENT_SECRET,
                "grant_type": "client_credentials",
            },
        )
        # TODO: exception token None
        token = request.json().get("access_token")
        return f"Bearer {token}"

    def get_headers(self):
        return {
            "Content-Type": "application/json; charset: utf-8",
            "Authorization": self.get_module_token(),
        }
