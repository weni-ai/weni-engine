import logging
import requests
import json
from django.conf import settings

from connect.api.v1.internal.internal_authentication import InternalAuthentication


logger = logging.getLogger(__name__)


class IntelligenceRESTClient:
    def __init__(self):
        self.base_url = settings.INTELLIGENCE_REST_ENDPOINT
        self.authentication_instance = InternalAuthentication()

    def list_organizations(self, user_email):
        response = requests.get(
            url=f"{self.base_url}v2/internal/organization/",
            headers=self.authentication_instance.headers,
            params={"user_email": user_email},
        )

        return response.json()

    def get_user_organization_permission_role(self, user_email, organization_id):
        response = requests.get(
            url=f"{self.base_url}v2/internal/user/permission/",
            headers=self.authentication_instance.headers,
            params={"user_email": user_email, "org_id": organization_id},
        )
        return response.json().get("role")

    def create_organization(self, user_email, organization_name):
        response = requests.post(
            url=f"{self.base_url}v2/internal/organization/",
            headers=self.authentication_instance.headers,
            json={"user_email": user_email, "organization_name": organization_name},
            params={"user_email": user_email},
        )
        return response.json()

    def delete_organization(self, organization_id, user_email):
        response = requests.delete(
            url=f"{self.base_url}v2/internal/organization/{organization_id}/",
            headers=self.authentication_instance.headers,
            params={"user_email": user_email},
        )
        return response.json()

    def update_organization(self, organization_id, organization_name, user_email):
        response = requests.put(
            url=f"{self.base_url}v2/internal/organization/{organization_id}/",
            headers=self.authentication_instance.headers,
            params={"user_email": user_email},
            json={"name": organization_name},
        )
        return response.json()

    def delete_user_permission(self, organization_id, user_email):
        params = dict(
            user_email=user_email,
            org_id=organization_id
        )
        requests.delete(
            url=f"{self.base_url}v2/internal/user/permissions",
            headers=self.authentication_instance.headers,
            params=params
        )

    def update_user_permission_organization(
        self, organization_id, user_email, permission
    ):
        response = requests.put(
            url=f"{self.base_url}v2/internal/user/permission/",
            headers=self.authentication_instance.headers,
            params={"org_id": organization_id, "user_email": user_email},
            json={"role": permission},
        )
        return response.json()

    def get_organization_intelligences(self, intelligence_name, organization_id):

        response = requests.get(
            url=f"{self.base_url}v2/internal/repository/",
            headers=self.authentication_instance.headers,
            params={"name": intelligence_name, "org_id": organization_id},
        )

        return response.json()

    def update_language(self, user_email, language):
        response = requests.put(
            url=f"{self.base_url}v2/internal/user/language/",
            headers=self.authentication_instance.headers,
            params={"user_email": user_email},
            json={"language": language},
        )
        return response.json()

    def get_organization_statistics(self, organization_id, user_email):
        response = requests.get(
            url=f"{self.base_url}v2/internal/organization/{organization_id}/",
            headers=self.authentication_instance.headers,
            params={"user_email": user_email},
        )
        return response.json().get("repositories_count", 0)

    def get_count_intelligences_project(self, classifiers):
        auth_list = set()
        for classifier in classifiers:
            response = requests.get(
                url=f"{self.base_url}v2/internal/repository/retrieve_authorization/",
                headers=self.authentication_instance.headers,
                params={
                    "repository_authorization": classifier.get("access_token")
                },
            )
            if response.status_code == 200:
                auth_list.add(response.json().get("uuid"))
            else:
                logger.error(f"{response.status_code}: classifier not found")
        return {"repositories_count": len(auth_list)}

    def get_access_token(self, user_email: str, repository_uuid: str):
        body = {
            "user_email": user_email,
            "repository_uuid": repository_uuid
        }
        response = requests.get(
            url=f"{self.base_url}v2/repository/authorization-by-user",
            headers=self.authentication_instance.headers,
            params=body
        )

        return json.loads(response.text).get("access_token")

    def create_project(self, project_uuid):
        from connect.common.models import Project
        project = Project.objects.get(uuid=project_uuid)
        body = {
            "project_uuid": project.uuuid,
            "name": project.name,
            "timezone": project.timezone,
            "is_template": project.is_template,
            "intelligence_organization": project.organization.inteligence_organization,
            "date_format": project.date_format,
            "created_by": project.create_by if project.created_by else "crm@weni.ai"
        }
        response = requests.post(
            url=f"{self.base_url}v2/project",
            headers=self.authentication_instance.headers,
            json=body
        )

        return response.json()

    def update_project(self, project_data):
        response = requests.patch(
            url=f"{self.base_url}v2/project",
            headers=self.authentication_instance.headers,
            json=project_data
        )
        return response.json()

    def delete_project(self, project_uuid):
        response = requests.delete(
            url=f"{self.base_url}v2/project",
            headers=self.authentication_instance.headers,
            json={"project_uuid": project_uuid}
        )
        return response.json()
