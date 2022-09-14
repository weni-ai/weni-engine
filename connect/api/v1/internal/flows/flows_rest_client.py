from django.conf import settings

import os
import requests

from connect.api.v1.internal.internal_authentication import InternalAuthentication
from connect.api.v1.internal.flows.helpers import add_classifier_to_flow


class FlowsRESTClient:

    sample_flow = f"{os.path.join(os.path.dirname(__file__))}/mp9/flows_definition_captura-de-leads.json"

    def __init__(self):
        self.base_url = settings.FLOWS_REST_ENDPOINT
        self.authentication_instance = InternalAuthentication()

    def create_template_project(self, project_name: str, user_email: str, project_timezone: str):
        body = dict(
            name=project_name,
            timezone=project_timezone,
            user_email=user_email
        )
        response = requests.post(
            url=f"{self.base_url}/api/v2/internals/template-orgs/",
            headers=self.authentication_instance.headers,
            json=body
        )
        return dict(status=response.status_code, data=response.text)

    def create_flows(self, project_uuid: str, classifier_uuid: str):

        sample_flow = add_classifier_to_flow(self.sample_flow, classifier_uuid)

        body = dict(
            org=project_uuid,
            sample_flow=sample_flow,
            classifier_uuid=classifier_uuid
        )
        response = requests.post(
            url=f"{self.base_url}/api/v2/internals/flows/",
            headers=self.authentication_instance.headers,
            json=body
        )
        return dict(status=response.status_code, data=response.text)

    def create_project(self, project_name: str, user_email: str, project_timezone: str):
        body = dict(
            name=project_name,
            timezone=project_timezone,
            user_email=user_email
        )

        response = requests.post(
            url=f"{self.base_url}/api/v2/internals/template-orgs/",
            headers=self.authentication_instance.headers,
            json=body
        )

        return dict(status=response.status_code, data=response.text)

    def update_project(self, organization_uuid: int, organization_name: str):
        body = {
            "uuid": organization_uuid
        }
        if organization_name:
            body['name'] = organization_name
        response = requests.patch(
            url=f"{self.base_url}/",
            headers=self.authentication_instance.headers,
            json=body
        )
        return dict(status=response.status_code, data=response.data)

    def delete_project(self, project_uuid: int, user_email: str):
        body = dict(
            uuid=project_uuid,
            user_email=user_email
        )

        response = requests.delete(
            url=f"{self.base_url}/",
            headers=self.authentication_instance.headers,
            json=body
        )

        return dict(status=response.status_code)

    def update_user_permission_project(self, organization_uuid: str, user_email: str, permission: int):
        permissions = {1: "viewer", 2: "editor", 3: "administrator"}

        body = dict(
            org_uuid=organization_uuid,
            user_email=user_email,
            permission=permissions.get(permission)
        )

        response = requests.delete(
            url=f"{self.base_url}/",
            headers=self.authentication_instance.headers,
            json=body
        )

        return dict(status=response.status_code, data=response.data)

    def get_classifiers(self, project_uuid: str, classifier_type: str, is_active: bool):

        body = dict(
            org_uuid=project_uuid,
            classifier_type=classifier_type,
            is_active=is_active,
        )

        response = requests.get(
            url=f"{self.base_url}/",
            headers=self.authentication_instance.headers,
            json=body
        )

        # TODO: check if response.data has a list with any element has: authorization_uuid, classifier_type, name, is_active, uuid
        return dict(status=response.status_code, data=response.data)

    def create_classifier(self, project_uuid: str, user_email: str, classifier_type: str, classifier_name: str, access_token: str):
        body = dict(
            org=project_uuid,
            user=user_email,
            classifier_type=classifier_type,
            name=classifier_name,
            access_token=access_token,
        )
        response = requests.post(
            url=f"{self.base_url}/",
            headers=self.authentication_instance.headers,
            json=body
        )
        # TODO: check the response data its equals to gRPC endpoint return
        return dict(status=response.status_code, data=response.data)

    def delete_classifier(self, classifier_uuid: str, user_email: str):
        body = dict(
            uuid=classifier_uuid,
            user_email=user_email
        )
        response = requests.delete(
            url=f"{self.base_url}/",
            headers=self.authentication_instance.headers,
            json=body
        )
        return dict(status=response.status_code)

    def create_ticketer(self, project_uuid, ticketer_type, name, config):
        body = dict(
            project_uuid=project_uuid,
            ticketer_type=ticketer_type,
            name=name,
            config=config
        )

        response = requests.post(
            url=f"{self.base_url}/",
            headers=self.authentication_instance.headers,
            json=body
        )

        return response.data