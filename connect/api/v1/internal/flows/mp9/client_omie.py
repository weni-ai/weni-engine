from django.conf import settings;from connect.api.v1.internal.flows.flows_rest_client import FlowsRESTClient;from connect.common.models import Project


class Omie:
    """ Client para fazer requests para criar template omie """

    def __init__(self):
        self.flows_rest = FlowsRESTClient()

    def create_globals(self, project_uuid: str, user_email: str, global_body: dict):
        body = {
            "org": project_uuid,
            "user": user_email,
        }

        omie_globals = []

        for key, value in global_body.items():

            payload = {
                "name": key,
                "value": value
            }

            payload.update(body)

            omie_globals.append(payload)

        response = self.flows_rest.create_globals(omie_globals)
        
        if response.status_code == 201:
            return response.json()

        raise Exception(response.json())