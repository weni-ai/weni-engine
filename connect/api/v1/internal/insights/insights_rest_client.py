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

    def notify_vtex_account_migration(self, project_uuid: str, vtex_account: str):
        """Notify Insights that a project was migrated to a VTEX account.

        TODO: the Insights endpoint is not finalized yet. This URL is
        temporary and must be swapped for the official route once the
        Insights team delivers it.
        """
        body = {
            "project_uuid": project_uuid,
            "vtex_account": vtex_account,
        }

        response = requests.post(
            url=f"{self.base_url}/v1/internal/vtex/migrate-account/",
            headers=self.authentication_instance.headers,
            json=body,
            timeout=60,
        )
        response.raise_for_status()

        return response.json()
