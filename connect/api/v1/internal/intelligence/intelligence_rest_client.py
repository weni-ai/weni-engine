from django.conf import settings

import requests
import json

from connect.api.v1.internal.internal_authencation import InternalAuthentication


class IntelligenceRESTClient:

    def __init__(self):
        self.base_url = settings.INTELLIGENCE_REST_ENDPOINT
        self.authentication_instance = InternalAuthentication()

    def list_organizations(self, user_email):
        response = requests.get(
            url=f"{self.base_url}v2/internal/organization/",
            headers=self.authentication_instance.get_headers(),
            params={"user_email": user_email}
        )

        return response.data

    def get_user_organization_permission_role(self, user_email, organization_id):
        response = requests.get(
            url=f"{self.base_url}v2/internal/user/permission/",
            headers=self.authentication_instance.get_headers(),
            params={"user_email": user_email, "organization_id": organization_id}
        )
        return response.data.role

    def create_organization(self, user_email, organization_name):
        response = requests.post(
            url=f"{self.base_url}v2/internal//organization/",
            headers=self.authentication_instance.get_headers(),
            json=json.dumps({"user_email": user_email, "organization_name": organization_name})
        )
        return response.data

    def delete_organization(self, organization_id, user_email):
        response = requests.delete(
            url=f"{self.base_url}v2/internal/{organization_id}/delete-organization/",
            headers=self.authentication_instance.get_headers(),
            params={"user_email": user_email}
        )
        return response

    def update_organization(self, organization_id, organization_name):
        response = requests.put(
            url=f"{self.base_url}v2/internal/{organization_id}/organization/",
            headers=self.authentication_instance.get_headers(),
            params={"organization_name": organization_name}
        )
        return response

    def update_user_permission_organization(
        self, organization_id, user_email, permission
    ):
        response = requests.put(
            url=f"{self.base_url}v2/internal/user/permission/",
            headers=self.authentication_instance.get_headers(),
            params={"organization_id": organization_id, "user_email": user_email},
            json=json.dumps({"role": permission})
        )
        return response.data

    def get_organization_intelligences(self, intelligence_name, organization_id):

        response = requests.get(
            url=f"{self.base_url}v2/internal/repository/",
            headers=self.authentication_instance.get_headers(),
            params={"intelligence_name": intelligence_name, "org_id": organization_id}
        )

        return response.data

    def update_language(self, user_email, language):
        response = requests.put(
            url=f"{self.base_url}v2/internal/user/language/",
            headers=self.authentication_instance.get_headers(),
            params={"user_email": user_email},
            json=json.dumps({"language": language})
        )
        return response.data

    def get_organization_statistics(self, organization_id):
        response = requests.get(
            url=f"{self.base_url}v2/internal/repository/",
            headers=self.authentication_instance.get_headers(),
            params={"organization_id": organization_id}
        )
        return len(response.data.repositories_count)

    def get_count_intelligences_project(self, classifiers):
        auth_list = set()
        for classifier in classifiers:
            response = requests.get(
                url=f"{self.base_url}v2/internal/repository/retrieve_authorization/",
                headers=self.authentication_instance.get_headers(),
                params={"repository_authorization": classifier.get('authorization_uuid')}
            )
            auth_list.add(response.data.uuid)
        return {"repositories_count": len(auth_list)}
