from connect import settings
from connect.internal.internal_authencation import InternalAuthentication

import requests
import json


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
        requests.patch(
            url=f"{self.base_url}api/v1/internal/user-permission/{project_uuid}/",
            headers=self.authentication_instance.get_headers(),
            json=json.dumps(body)
        )
        return True

    def update_user(self, user_email, photo_url, first_name, last_name):
        body = {
            "email": user_email,
            "photo_url": photo_url,
            "first_name": first_name,
            "last_name": last_name
        }
        requests.post(
            url=f"{self.base_url}api/v1/internal/user/",
            headers=self.authentication_instance.get_headers(),
            json=json.dumps(body)
        )
