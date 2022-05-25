from connect import settings
from connect.internal.internal_authencation import InternalAuthentication

import requests


class IntelligenceRESTClient:

    def __init__(self):
        self.base_url = settings.INTELIGENCE_REST_ENDPOINT
        self.authentication_instance = InternalAuthentication()

    def list_organizations(self, user_email):

        response = requests.get(
            url=f"{self.base_url}/v2/internal/list-organizations",
            headers=self.authentication_instance.get_headers(),
            params={"user_email": user_email}
        )

        return response

    def get_user_organization_permission_role(self, user_email, organization_id):
        response = requests.get(
            url=f"{self.base_url}/v2/internal/get-user-organization-permission-role",
            headers=self.authentication_instance.get_headers(),
            params={"user_email": user_email, "organization_id": organization_id}
        )
        
        return response
    
    def create_organization(self, user_email, organization_name):
        response = requests.post(
            url=f"{self.base_url}/v2/internal/create-organization",
            headers.self.authentication_instance.get_headers(),
            json=json.dumps({"user_email": user_email, "organization_name": organization_name})
        )
        return response

    def delete_organization(self, organization_id, user_email):
        response = requests.delete(
            url=f"{self.base_url}/v2/internal/delete-organization",
            headers=self.authentication_instance.get_headers(),
            json=json.dumps({"user_email": user_email, "organization_id": organization_id})
        )