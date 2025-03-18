import requests

from django.conf import settings

from connect.api.v1.internal.internal_authentication import InternalAuthentication


class InsightsRESTClient:
    def __init__(self):
        self.base_url = settings.INSIGHTS_REST_ENDPOINT
        self.authentication_instance = InternalAuthentication()

    def update_user_language(self, user_email: str, language: str):
        body = dict(email=user_email, language=language)

        requests.post(
            url=f"{self.base_url}/v1/internal/users/change-language/",
            headers=self.authentication_instance.headers,
            json=body,
        )
