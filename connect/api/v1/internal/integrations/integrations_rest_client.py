from django.conf import settings

import requests

from connect.api.v1.internal.internal_authentication import InternalAuthentication


class IntegrationsRESTClient:

    def __init__(self):
        self.base_url = settings.INTEGRATIONS_REST_ENDPOINT
        self.authentication_instance = InternalAuthentication()

    def update_user_permission_project(self, project_uuid, user_email, role):
        body = {
            "project_uuid": project_uuid,
            "user": user_email,
            "role": role
        }
        response = requests.patch(
            url=f"{self.base_url}/api/v1/internal/user-permission/{project_uuid}/",
            headers=self.authentication_instance.headers(),
            json=body
        )
        return dict(status=response.status_code)

    def update_user(self, user_email, photo_url=None, first_name=None, last_name=None):
        body = {
            "email": user_email,
        }

        if photo_url:
            body["photo_url"] = photo_url

        if first_name:
            body["first_name"] = first_name

        if last_name:
            body["last_name"] = last_name

        response = requests.post(
            url=f"{self.base_url}/api/v1/internal/user/",
            headers=self.authentication_instance.headers(),
            json=body
        )
        response.raise_for_status()
        return dict(status=response.status_code)
