import json
import uuid

from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.response import Response

from django.test import TestCase

from unittest.mock import patch

from connect.api.v1.tests.utils import create_user_and_token
from connect.common.models import Organization, BillingPlan, OrganizationRole, Project
from connect.api.v2.organizations.views import OrganizationViewSet


class OrganizationViewSetTestCase(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user, self.user_token = create_user_and_token("user")
        self.user_1, self.user_1_token = create_user_and_token("user_1")
        self.user_403, self.user_403_token = create_user_and_token("user_403")

        self.org_1 = Organization.objects.create(
            name="V2 Org 1",
            description="V2 Org 1",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )

        self.org_2 = Organization.objects.create(
            name="V2 Org 2",
            description="V2 Org 2",
            inteligence_organization=2,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_ADVANCED,
        )

        self.org_3 = Organization.objects.create(
            name="V2 Org 3",
            description="V2 Org 3",
            inteligence_organization=3,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_SCALE,
        )

        self.org_auth_1 = self.org_1.authorizations.create(
            user=self.user, role=OrganizationRole.ADMIN.value
        )

        self.org_auth_2 = self.org_2.authorizations.create(
            user=self.user, role=OrganizationRole.CONTRIBUTOR.value
        )

    def make_request(self, path, method, data):
        for key in method:
            if key == "post":
                request = self.factory.post(path, data, format="json")
            elif key == "delete":
                request = self.factory.delete(path)
            else:
                request = self.factory.get(path)
            return request

    def request(self, path: str, method: dict, pk: str = None, data: dict = None, user=None):
        content_data = ""

        if pk:
            path += f"{pk}"

        request = self.make_request(path, method, data)

        force_authenticate(request, user=user, token=user.auth_token)

        response = OrganizationViewSet.as_view(method)(request, uuid=pk, data=data)
        response.render()

        if not response.status_code == status.HTTP_204_NO_CONTENT:
            content_data = json.loads(response.content)
        return response, content_data

    def test_get_organization(self):
        pk = str(self.org_1.uuid)
        path = "/v2/organizations/"
        method = {"get": "retrieve"}
        user = self.user
        auth = self.org_1.get_user_authorization(self.user)
        response, content_data = self.request(
            path,
            method,
            pk=pk,
            user=user
        )

        self.assertEquals(response.status_code, status.HTTP_200_OK)
        self.assertEquals(content_data.get("authorization").get("uuid"), str(auth.uuid))
        self.assertEquals(content_data.get("uuid"), pk)

    def test_fail_get_authorization(self):
        pk = str(self.org_1.uuid)
        path = "/v2/organizations/"
        method = {"get": "retrieve"}
        user = self.user_403

        response, content_data = self.request(
            path,
            method,
            pk=pk,
            user=user
        )
        self.assertEquals(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_organizations(self):
        path = "/v2/organizations/"
        method = {"get": "list"}
        user = self.user
        response, content_data = self.request(
            path,
            method,
            user=user
        )
        self.assertEquals(response.status_code, status.HTTP_200_OK)
        self.assertEquals(content_data.get("count"), 2)

    @patch("connect.authentication.models.User.send_request_flow_user_info")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_project")
    def test_create_organization_blank_project(self, flows_info, send_request_flow_user_info):
        flows_info.side_effect = [{"id": 1, "uuid": uuid.uuid4()}]
        send_request_flow_user_info.side_effect = [True]
        org_data = {
            "name": "V2",
            "description": "V2 desc",
            "organization_billing_plan": BillingPlan.PLAN_TRIAL,
            "authorizations": [
                {"user_email": "e@mail.com", "role": 3},
                {"user_email": "user_1@user.com", "role": 3}
            ],
        }

        project_data = {
            "date_format": "D",
            "name": "Test Project",
            "timezone": "America/Argentina/Buenos_Aires",
        }

        data = {
            "organization": org_data,
            "project": project_data
        }

        path = "/v2/organizations/"
        method = {"post": "create"}
        user = self.user

        response, content_data = self.request(
            path,
            method,
            user=user,
            data=data
        )

        organization = content_data.get("organization")

        self.assertEquals(response.status_code, status.HTTP_201_CREATED)
        self.assertEquals(organization["authorizations"]["count"], 2)

    @patch("connect.api.v1.internal.integrations.integrations_rest_client.IntegrationsRESTClient.whatsapp_demo_integration")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_flows")
    @patch("connect.api.v1.internal.chats.chats_rest_client.ChatsRESTClient.create_chat_project")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_classifier")
    @patch("connect.common.models.Organization.get_ai_access_token")
    @patch("connect.authentication.models.User.send_request_flow_user_info")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_project")
    def test_create_organization_lead_project(self, flows_info, send_request_flow_user_info, get_ai_access_token, create_classifier, create_chat_project, create_flows, wpp_integration):
        data = {
            "redirect_url": "https://example.com",
            "router_token": "rt_token"
        }

        flows_info.side_effect = [{"id": 1, "uuid": uuid.uuid4()}]
        send_request_flow_user_info.side_effect = [True]
        get_ai_access_token.side_effect = [(True, str(uuid.uuid4()))]
        create_classifier.side_effect = [{"data": {"uuid": uuid.uuid4()}}]
        wpp_integration.side_effect = [data]

        chats_data = {
            "ticketer": {"uuid": str(uuid.uuid4()), "name": "Test Ticketer"},
            "queue": {"uuid": str(uuid.uuid4()), "name": "Test Queue"},
        }

        class Response:
            text = json.dumps(chats_data)

        flows_response = '{"uuid": "9785a273-37de-4658-bfa2-d8028dc06c84"}'
        create_chat_project.side_effect = [Response()]

        create_flows.side_effect = [dict(status=201, data=flows_response)]

        org_data = {
            "name": "V2",
            "description": "V2 desc",
            "organization_billing_plan": BillingPlan.PLAN_TRIAL,
            "authorizations": [
                {"user_email": "e@mail.com", "role": 3},
                {"user_email": "user_1@user.com", "role": 3}
            ],
        }

        project_data = {
            "date_format": "D",
            "name": "Test Project",
            "timezone": "America/Argentina/Buenos_Aires",
            "template": True,
            "template_type": Project.TYPE_LEAD_CAPTURE
        }

        data = {
            "organization": org_data,
            "project": project_data
        }

        path = "/v2/organizations/"
        method = {"post": "create"}
        user = self.user

        response, content_data = self.request(
            path,
            method,
            user=user,
            data=data
        )

        organization = content_data.get("organization")

        self.assertEquals(response.status_code, status.HTTP_201_CREATED)
        self.assertEquals(organization["authorizations"]["count"], 2)

    @patch("connect.api.v2.projects.serializers.TemplateProjectSerializer.validate_project_authorization")
    @patch("connect.authentication.models.User.send_request_flow_user_info")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_project")
    def test_create_organization_lead_project_fail_auth(self, flows_info, send_request_flow_user_info, validate_authorization=None):
        flows_info.side_effect = [{"id": 1, "uuid": uuid.uuid4()}]
        send_request_flow_user_info.side_effect = [True]
        validate_authorization.side_effect = [(False, {
            "message": "Project authorization not setted",
            "status": status.HTTP_500_INTERNAL_SERVER_ERROR
        })]

        org_data = {
            "name": "V2",
            "description": "V2 desc",
            "organization_billing_plan": BillingPlan.PLAN_TRIAL,
            "authorizations": [
                {"user_email": "e@mail.com", "role": 3},
                {"user_email": "user_1@user.com", "role": 3}
            ],
        }

        project_data = {
            "date_format": "D",
            "name": "Test Project",
            "timezone": "America/Argentina/Buenos_Aires",
            "template": True,
            "template_type": Project.TYPE_LEAD_CAPTURE
        }

        data = {
            "organization": org_data,
            "project": project_data
        }

        path = "/v2/organizations/"
        method = {"post": "create"}
        user = self.user

        response, content_data = self.request(
            path,
            method,
            user=user,
            data=data
        )

        self.assertEquals(int(response.status_code), status.HTTP_500_INTERNAL_SERVER_ERROR)

    # @patch("connect.api.v2.projects.serializers.TemplateProjectSerializer.validate_project_authorization")

    @patch("connect.common.models.Organization.get_ai_access_token")
    @patch("connect.authentication.models.User.send_request_flow_user_info")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_project")
    def test_create_organization_lead_project_fail_access_token(self, flows_info, send_request_flow_user_info, get_ai_access_token):
        flows_info.side_effect = [{"id": 1, "uuid": uuid.uuid4()}]
        send_request_flow_user_info.side_effect = [True]
        get_ai_access_token.side_effect = [(False, {
            "message": "Could not get access token",
            "status": status.HTTP_500_INTERNAL_SERVER_ERROR
        })]

        org_data = {
            "name": "V2",
            "description": "V2 desc",
            "organization_billing_plan": BillingPlan.PLAN_TRIAL,
            "authorizations": [
                {"user_email": "e@mail.com", "role": 3},
                {"user_email": "user_1@user.com", "role": 3}
            ],
        }

        project_data = {
            "date_format": "D",
            "name": "Test Project",
            "timezone": "America/Argentina/Buenos_Aires",
            "template": True,
            "template_type": Project.TYPE_LEAD_CAPTURE
        }

        data = {
            "organization": org_data,
            "project": project_data
        }

        path = "/v2/organizations/"
        method = {"post": "create"}
        user = self.user

        response, content_data = self.request(
            path,
            method,
            user=user,
            data=data
        )

        self.assertEquals(int(response.status_code), status.HTTP_500_INTERNAL_SERVER_ERROR)

    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_project")
    def test_create_organization_fail_create_project(self, flows_info):
        flows_info.side_effect = [Exception("Error")]
        org_data = {
            "name": "V2",
            "description": "V2 desc",
            "organization_billing_plan": BillingPlan.PLAN_TRIAL,
            "authorizations": [
                {"user_email": "e@mail.com", "role": 3},
                {"user_email": "user_1@user.com", "role": 3}
            ],
        }

        project_data = {
            "date_format": "D",
            "name": "Test Project",
            "timezone": "America/Argentina/Buenos_Aires",
        }

        data = {
            "organization": org_data,
            "project": project_data
        }

        path = "/v2/organizations/"
        method = {"post": "create"}
        user = self.user

        response, content_data = self.request(
            path,
            method,
            user=user,
            data=data
        )
        self.assertEquals(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_classifier")
    @patch("connect.common.models.Organization.get_ai_access_token")
    @patch("connect.authentication.models.User.send_request_flow_user_info")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_project")
    def test_create_organization_lead_project_fail_create_classifier(self, flows_info, send_request_flow_user_info, get_ai_access_token, create_classifier):
        flows_info.side_effect = [{"id": 1, "uuid": uuid.uuid4()}]
        send_request_flow_user_info.side_effect = [True]
        get_ai_access_token.side_effect = [(True, str(uuid.uuid4()))]
        create_classifier.side_effect = [Exception()]
        org_data = {
            "name": "V2",
            "description": "V2 desc",
            "organization_billing_plan": BillingPlan.PLAN_TRIAL,
            "authorizations": [
                {"user_email": "e@mail.com", "role": 3},
                {"user_email": "user_1@user.com", "role": 3}
            ],
        }

        project_data = {
            "date_format": "D",
            "name": "Test Project",
            "timezone": "America/Argentina/Buenos_Aires",
            "template": True,
            "template_type": Project.TYPE_LEAD_CAPTURE
        }

        data = {
            "organization": org_data,
            "project": project_data
        }

        path = "/v2/organizations/"
        method = {"post": "create"}
        user = self.user

        response, content_data = self.request(
            path,
            method,
            user=user,
            data=data
        )
        self.assertEquals(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    @patch("connect.common.models.Project.create_flows")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_classifier")
    @patch("connect.common.models.Organization.get_ai_access_token")
    @patch("connect.authentication.models.User.send_request_flow_user_info")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_project")
    def test_create_organization_lead_project_fail_create_flows(self, flows_info, send_request_flow_user_info, get_ai_access_token, create_classifier, create_flows):
        flows_info.side_effect = [{"id": 1, "uuid": uuid.uuid4()}]
        send_request_flow_user_info.side_effect = [True]
        get_ai_access_token.side_effect = [(True, str(uuid.uuid4()))]
        create_classifier.side_effect = [{"data": {"uuid": uuid.uuid4()}}]
        response_data = {
            "message": "Could not create flow",
            "status": status.HTTP_500_INTERNAL_SERVER_ERROR
        }
        create_flows.side_effect = [(False, response_data)]
        org_data = {
            "name": "V2",
            "description": "V2 desc",
            "organization_billing_plan": BillingPlan.PLAN_TRIAL,
            "authorizations": [
                {"user_email": "e@mail.com", "role": 3},
                {"user_email": "user_1@user.com", "role": 3}
            ],
        }

        project_data = {
            "date_format": "D",
            "name": "Test Project",
            "timezone": "America/Argentina/Buenos_Aires",
            "template": True,
            "template_type": Project.TYPE_LEAD_CAPTURE
        }

        data = {
            "organization": org_data,
            "project": project_data
        }

        path = "/v2/organizations/"
        method = {"post": "create"}
        user = self.user

        response, content_data = self.request(
            path,
            method,
            user=user,
            data=data
        )
        self.assertEquals(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEquals(content_data, response_data.get("message"))

    @patch("connect.common.models.Project.whatsapp_demo_integration")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_flows")
    @patch("connect.api.v1.internal.chats.chats_rest_client.ChatsRESTClient.create_chat_project")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_classifier")
    @patch("connect.common.models.Organization.get_ai_access_token")
    @patch("connect.authentication.models.User.send_request_flow_user_info")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_project")
    def test_create_organization_lead_project_fail_integrate_wpp(self, flows_info, send_request_flow_user_info, get_ai_access_token, create_classifier, create_chat_project, create_flows, wpp_integration):
        response_data = {
            "message": "Could not create flow",
            "status": status.HTTP_500_INTERNAL_SERVER_ERROR
        }

        flows_info.side_effect = [{"id": 1, "uuid": uuid.uuid4()}]
        send_request_flow_user_info.side_effect = [True]
        get_ai_access_token.side_effect = [(True, str(uuid.uuid4()))]
        create_classifier.side_effect = [{"data": {"uuid": uuid.uuid4()}}]
        wpp_integration.side_effect = [(False, response_data)]

        chats_data = {
            "ticketer": {"uuid": str(uuid.uuid4()), "name": "Test Ticketer"},
            "queue": {"uuid": str(uuid.uuid4()), "name": "Test Queue"},
        }

        class Response:
            text = json.dumps(chats_data)

        flows_response = '{"uuid": "9785a273-37de-4658-bfa2-d8028dc06c84"}'
        create_chat_project.side_effect = [Response()]

        create_flows.side_effect = [dict(status=201, data=flows_response)]

        org_data = {
            "name": "V2",
            "description": "V2 desc",
            "organization_billing_plan": BillingPlan.PLAN_TRIAL,
            "authorizations": [
                {"user_email": "e@mail.com", "role": 3},
                {"user_email": "user_1@user.com", "role": 3}
            ],
        }

        project_data = {
            "date_format": "D",
            "name": "Test Project",
            "timezone": "America/Argentina/Buenos_Aires",
            "template": True,
            "template_type": Project.TYPE_LEAD_CAPTURE
        }

        data = {
            "organization": org_data,
            "project": project_data
        }

        path = "/v2/organizations/"
        method = {"post": "create"}
        user = self.user

        response, content_data = self.request(
            path,
            method,
            user=user,
            data=data
        )

        self.assertEquals(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEquals(content_data, response_data.get("message"))

    @patch("connect.api.v1.internal.intelligence.intelligence_rest_client.IntelligenceRESTClient.delete_organization")
    def test_perform_destroy(self, ai_destroy):
        ai_destroy.side_effect = [Response(data={}, status=status.HTTP_204_NO_CONTENT)]
        pk = str(self.org_1.uuid)
        path = "/v2/organizations/"
        method = {"delete": "destroy"}
        user = self.user

        response, content_data = self.request(
            path,
            method,
            pk=pk,
            user=user
        )
