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
            url=f"{self.base_url}/api/v2/internals/orgs/",
            headers=self.authentication_instance.headers,
            json=body
        )

        return response.json()

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
            user_email=user_email
        )

        response = requests.delete(
            url=f"{self.base_url}/api/v2/internals/orgs/{project_uuid}/",
            headers=self.authentication_instance.headers,
            params=body
        )

        return dict(status=response.status_code)

    def update_user_permission_project(self, organization_uuid: str, user_email: str, permission: int):
        permissions = {1: "viewer", 2: "editor", 3: "administrator", 4: "administrator", 5: "agent"}

        body = dict(
            org_uuid=organization_uuid,
            user_email=user_email,
            permission=permissions.get(permission)
        )
        response = requests.patch(
            url=f"{self.base_url}/api/v2/internals/user-permission/",
            headers=self.authentication_instance.headers,
            json=body
        )

        return dict(status=response.status_code, data=response.json())

    def get_classifiers(self, project_uuid: str, classifier_type: str, is_active: bool):

        params = dict(
            org_uuid=project_uuid,
            classifier_type=classifier_type,
            is_active=is_active,
        )

        response = requests.get(
            url=f"{self.base_url}/api/v2/internals/classifier/",
            headers=self.authentication_instance.headers,
            params=params
        )

        return response.json()

    def create_classifier(self, project_uuid: str, user_email: str, classifier_type: str, classifier_name: str, access_token: str):
        body = dict(
            org=project_uuid,
            user=user_email,
            classifier_type=classifier_type,
            name=classifier_name,
            access_token=access_token,
        )
        response = requests.post(
            url=f"{self.base_url}/api/v2/internals/classifier/",
            headers=self.authentication_instance.headers,
            json=body
        )
        # TODO: check the response data its equals to gRPC endpoint return
        return dict(status=response.status_code, data=response.json())

    def delete_classifier(self, classifier_uuid: str, user_email: str):
        body = dict(
            uuid=classifier_uuid,
            user_email=user_email
        )
        response = requests.delete(
            url=f"{self.base_url}/api/v2/internals/classifier/",
            headers=self.authentication_instance.headers,
            json=body
        )
        return dict(status=response.status_code)

    def get_user_api_token(self, project_uuid: str, user_email: str):
        params = dict(org=project_uuid, user=user_email)
        response = requests.get(
            url=f"{self.base_url}/api/v2/internals/users/api-token",
            params=params,
            headers=self.authentication_instance.headers
        )
        return response

    def create_ticketer(self, project_uuid, ticketer_type, name, config):
        body = dict(
            org=project_uuid,
            ticketer_type=ticketer_type,
            name=name,
            config=config
        )

        response = requests.post(
            url=f"{self.base_url}/api/v2/internals/ticketers/",
            headers=self.authentication_instance.headers,
            json=body
        )

        return response.json()

    def update_language(self, user_email: str, language: str):
        body = dict(
            language=language
        )
        params = dict(
            email=user_email
        )
        response = requests.patch(
            url=f'{self.base_url}/api/v2/internals/flows-users/',
            headers=self.authentication_instance.headers,
            params=params,
            json=body
        )
        return response.status_code

    def get_project_flows(self, project_uuid, flow_name):
        params = dict(
            flow_name=flow_name,
            org_uuid=project_uuid
        )
        response = requests.get(
            url=f"{self.base_url}/api/v2/internals/project-flows/",
            headers=self.authentication_instance.headers,
            params=params
        )
        return response.json()

    def get_project_info(self, project_uuid: str):
        response = requests.get(
            url=f'{self.base_url}/api/v2/internals/orgs/{project_uuid}/',
            headers=self.authentication_instance.headers,
        )
        return response.json()

    def get_project_statistic(self, project_uuid: str):
        response = requests.get(
            url=f'{self.base_url}/api/v2/internals/statistic/{project_uuid}/',
            headers=self.authentication_instance.headers,
        )
        return response.json()

    def get_billing_total_statistics(self, project_uuid: str, before: str, after: str):
        body = dict(
            org=project_uuid,
            before=before,
            after=after
        )
        response = requests.get(
            url=f'{self.base_url}/',
            headers=self.authentication_instance.headers,
            json=body
        )
        return response.json()

    def suspend_or_unsuspend_project(self, project_uuid: str, is_suspended: bool):
        body = dict(
            uuid=project_uuid,
            is_suspended=is_suspended
        )
        response = requests.patch(
            url=f'{self.base_url}/api/v2/internals/orgs/{project_uuid}/',
            headers=self.authentication_instance.headers,
            json=body
        )
        return response.json()

    def create_channel(self, user: str, project_uuid: str, data: dict, channeltype_code: str):
        body = dict(
            user=user,
            org=project_uuid,
            data=data,
            channeltype_code=channeltype_code
        )
        response = requests.post(
            url=f'{self.base_url}/api/v2/internals/channel/',
            headers=self.authentication_instance.headers,
            json=body
        )
        return response

    def create_wac_channel(self, user: str, flow_organization: str, config: str, phone_number_id: str):
        body = dict(
            user=user,
            org=flow_organization,
            config=config,
            phone_number_id=phone_number_id,
        )
        response = requests.post(
            url=f'{self.base_url}/api/v2/internals/channel/create_wac/',
            headers=self.authentication_instance.headers,
            json=body
        )
        return response.json()

    def release_channel(self, user: str, channel_uuid: str):
        requests.delete(
            url=f'{self.base_url}/api/v2/internals/channel/{channel_uuid}/',
            headers=self.authentication_instance.headers,
            json={"user": user}
        )

    def list_channel(self, is_active: str = "True", channel_type: str = "WA", project_uuid: str = None):
        params = {}
        if project_uuid:
            params = dict(
                is_active=is_active,
                channel_type=channel_type,
                org=project_uuid
            )
        else:
            params = dict(
                is_active=is_active,
                channel_type=channel_type
            )
        response = requests.get(
            url=f'{self.base_url}/api/v2/internals/channel/',
            headers=self.authentication_instance.headers,
            params=params
        )
        return response.json()

    def delete_channel(self, channel_uuid: str):
        response = requests.delete(
            url=f'{self.base_url}/api/v2/internals/channel/{channel_uuid}/',
            headers=self.authentication_instance.headers
        )
        return response.json()

    def get_active_contacts(self, project_uuid, before, after):
        body = dict(
            org=project_uuid,
            before=before,
            after=after
        )
        response = requests.get(
            url=f'{self.base_url}/api/v2/internals/',
            headers=self.authentication_instance.headers,
            json=body
        )
        return response.get("data", [])

    def delete_user_permission_project(self, project_uuid: str, user_email: str, permission: int):
        permissions = {1: "viewer", 2: "editor", 3: "administrator", 4: "administrator", 5: "agent"}
        body = dict(
            org_uuid=project_uuid,
            user_email=user_email,
            permission=permissions.get(permission),
        )
        response = requests.delete(
            url=f'{self.base_url}/api/v2/internals/user-permission/',
            headers=self.authentication_instance.headers,
            json=body
        )
        return response.json()

    def get_message(self, org_uuid: str, contact_uuid: str, before: str, after: str):
        body = dict(
            org_uuid=org_uuid,
            contact_uuid=contact_uuid,
            before=before,
            after=after
        )
        response = requests.get(
            url=f'{self.base_url}/',
            headers=self.authentication_instance.headers,
            json=body
        )
        return response.json()
