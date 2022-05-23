from connect import settings
from connect.internal.internal_authencation import InternalAuthentication

import requests


class IntelligenceRESTClient:

    def __init__(self):
        self.base_url = settings.INTELIGENCE_REST_ENDPOINT
        self.authentication_instance = InternalAuthentication()

    def list_organizations(self, user_email: str):
        result = []

        request = requests.get(
            url=f"{self.base_url}/v2/internal/list-organizations",
            headers=self.authentication_instance.get_headers(),
            params={"user_email": user_email}
        )

        print(request)

        return result
