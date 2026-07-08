from typing import Optional

import requests

from django.conf import settings

from connect.api.v1.internal.internal_authentication import InternalAuthentication


class InsightsRESTClient:
    """
    REST client for Insights API
    """

    def __init__(self):
        self.base_url = settings.INSIGHTS_REST_ENDPOINT
        self.authentication_instance = InternalAuthentication()

    def update_user_language(self, user_email: str, language: str):
        """
        Update the language of a user
        """
        body = dict(email=user_email, language=language)

        response = requests.post(
            url=f"{self.base_url}/v1/internal/users/change-language/",
            headers=self.authentication_instance.headers,
            json=body,
            timeout=60,
        )

        return response.json()

    def notify_vtex_account_migration(
        self, project_uuid: str, vtex_account: Optional[str]
    ) -> dict:
        """Sync the project VTEX account to Insights after a Connect migration."""
        response = requests.patch(
            url=f"{self.base_url}/v1/internal/projects/{project_uuid}/vtex-account",
            headers=self.authentication_instance.headers,
            json={"vtex_account": vtex_account},
            timeout=60,
        )
        response.raise_for_status()

        if not response.content:
            return {}
        return response.json()
