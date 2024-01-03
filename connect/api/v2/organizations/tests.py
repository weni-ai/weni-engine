import json
import uuid

from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.response import Response

from django.test import TestCase

from unittest.mock import patch

from connect.api.v1.tests.utils import create_user_and_token
from connect.common.models import Organization, BillingPlan, OrganizationRole, Project
from connect.authentication.models import UserEmailSetup
from connect.api.v2.organizations.views import OrganizationViewSet
from connect.common.mocks import StripeMockGateway

from django.conf import settings
from connect.api.v1.tests.utils import create_contacts
from connect.billing.tasks import daily_contact_count
import pendulum


class OrganizationViewSetTestCase(TestCase):

    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway):
        mock_get_gateway.return_value = StripeMockGateway()

        self.integrations_rest = patch("connect.api.v1.internal.integrations.integrations_rest_client.IntegrationsRESTClient.update_user_permission_project")
        self.flows_rest = patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.update_user_permission_project")
        self.integrations_rest_mock = self.integrations_rest.start()
        self.flows_rest_mock = self.flows_rest.start()
        self.integrations_rest_mock.return_value = [200, 200]
        self.flows_rest_mock.return_value = [200, 200]

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

    @patch("connect.billing.get_gateway")
    @patch("connect.authentication.models.User.send_request_flow_user_info")
    def test_create_organization_blank_project(
        self, send_request_flow_user_info, mock_get_gateway
    ):
        mock_get_gateway.return_value = StripeMockGateway()
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

        self.assertEquals(response.status_code, status.HTTP_201_CREATED)

    @patch("connect.billing.get_gateway")
    @patch("connect.api.v1.internal.intelligence.intelligence_rest_client.IntelligenceRESTClient.create_organization")
    @patch("connect.authentication.models.User.send_request_flow_user_info")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_project")
    def test_create_organization_ai_blank_project(
        self, create_project, send_request_flow_user_info, create_organization, mock_get_gateway
    ):
        mock_get_gateway.return_value = StripeMockGateway()
        intelligence_organization = 555
        create_project.side_effect = [{"id": 1, "uuid": uuid.uuid4()}]
        create_organization.side_effect = [{"id": intelligence_organization}]
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

        settings.CREATE_AI_ORGANIZATION = True
        response, content_data = self.request(
            path,
            method,
            user=user,
            data=data
        )
        organization = content_data.get("organization")
        settings.CREATE_AI_ORGANIZATION = False
        self.assertEquals(response.status_code, status.HTTP_201_CREATED)
        self.assertEquals(organization["inteligence_organization"], intelligence_organization)

    @patch("connect.billing.get_gateway")
    @patch("connect.api.v1.internal.integrations.integrations_rest_client.IntegrationsRESTClient.whatsapp_demo_integration")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_flows")
    @patch("connect.api.v1.internal.chats.chats_rest_client.ChatsRESTClient.create_chat_project")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_classifier")
    @patch("connect.common.models.Organization.get_ai_access_token")
    @patch("connect.authentication.models.User.send_request_flow_user_info")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_template_project")
    @patch("connect.api.v1.internal.intelligence.intelligence_rest_client.IntelligenceRESTClient.create_organization")
    def test_create_organization_lead_project(
        self, create_organization, flows_info,
        send_request_flow_user_info, get_ai_access_token,
        create_classifier, create_chat_project,
        create_flows, wpp_integration, mock_get_gateway
    ):
        mock_get_gateway.return_value = StripeMockGateway()
        data = {
            "redirect_url": "https://example.com",
            "router_token": "rt_token"
        }
        create_organization.side_effect = [{"id": 1}]
        flows_info.side_effect = [{"data": '{"id": 1, "uuid": "6b6a8c8b-6734-4110-81c9-287eaeab8e26"}'}]
        send_request_flow_user_info.side_effect = [True]
        get_ai_access_token.side_effect = [(True, str(uuid.uuid4()))]
        create_classifier.side_effect = [{"status": 201, "data": {"uuid": "fdd4a7bb-fe5a-41b1-96a2-96d95c4e7aab"}}]
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

    @patch("connect.billing.get_gateway")
    @patch("connect.api.v1.internal.integrations.integrations_rest_client.IntegrationsRESTClient.whatsapp_demo_integration")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_flows")
    @patch("connect.api.v1.internal.chats.chats_rest_client.ChatsRESTClient.create_chat_project")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_classifier")
    @patch("connect.common.models.Organization.get_ai_access_token")
    @patch("connect.authentication.models.User.send_request_flow_user_info")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_template_project")
    @patch("connect.api.v1.internal.intelligence.intelligence_rest_client.IntelligenceRESTClient.create_organization")
    def test_create_organization_lead_capture_chat_gpt(
        self, create_organization, flows_info, send_request_flow_user_info,
        get_ai_access_token, create_classifier, create_chat_project,
        create_flows, wpp_integration, mock_get_gateway
    ):
        mock_get_gateway.return_value = StripeMockGateway()
        data = {
            "redirect_url": "https://example.com",
            "router_token": "rt_token"
        }
        create_organization.side_effect = [{"id": 1}]
        flows_info.side_effect = [{"data": '{"id": 1, "uuid": "6b6a8c8b-6734-4110-81c9-287eaeab8e26"}'}]
        send_request_flow_user_info.side_effect = [True]
        get_ai_access_token.side_effect = [(True, str(uuid.uuid4()))]
        create_classifier.side_effect = [{"status": 201, "data": {"uuid": "fdd4a7bb-fe5a-41b1-96a2-96d95c4e7aab"}}]
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
    @patch("connect.common.signals.update_user_permission_project")
    @patch("connect.billing.get_gateway")
    @patch("connect.authentication.models.User.send_request_flow_user_info")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_template_project")
    def test_create_organization_lead_project_fail_auth(
        self, flows_info,
        send_request_flow_user_info, mock_get_gateway,
        mock_permission, validate_authorization=None,
    ):
        mock_get_gateway.return_value = StripeMockGateway()
        mock_permission.return_value = True
        flows_info.side_effect = [{"data": '{"id": 1, "uuid": "6b6a8c8b-6734-4110-81c9-287eaeab8e26"}'}]
        send_request_flow_user_info.side_effect = [True]
        validate_authorization.side_effect = [(False, {
            "data": {"message": "Project authorization not setted"},
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

    @patch("connect.billing.get_gateway")
    @patch("connect.common.models.Organization.get_ai_access_token")
    @patch("connect.authentication.models.User.send_request_flow_user_info")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_template_project")
    @patch("connect.api.v1.internal.intelligence.intelligence_rest_client.IntelligenceRESTClient.create_organization")
    def test_create_organization_lead_project_fail_access_token(
        self, create_organization, flows_info,
        send_request_flow_user_info, get_ai_access_token,
        mock_get_gateway
    ):
        mock_get_gateway.return_value = StripeMockGateway()
        create_organization.side_effect = [{"id": 1}]
        flows_info.side_effect = [{"data": '{"id": 1, "uuid": "6b6a8c8b-6734-4110-81c9-287eaeab8e26"}'}]
        send_request_flow_user_info.side_effect = [True]
        get_ai_access_token.side_effect = [(False, {
            "data": {"message": "Could not get access token"},
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

    @patch("connect.billing.get_gateway")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_project")
    def test_create_organization_fail_create_project(self, flows_info, mock_get_gateway):
        mock_get_gateway.return_value = StripeMockGateway()
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

    @patch("connect.billing.get_gateway")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_classifier")
    @patch("connect.common.models.Organization.get_ai_access_token")
    @patch("connect.authentication.models.User.send_request_flow_user_info")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_template_project")
    def test_create_organization_lead_project_fail_create_classifier(
        self, flows_info, send_request_flow_user_info,
        get_ai_access_token, create_classifier, mock_get_gateway
    ):
        mock_get_gateway.return_value = StripeMockGateway()
        flows_info.side_effect = [{"data": '{"id": 1, "uuid": "6b6a8c8b-6734-4110-81c9-287eaeab8e26"}'}]
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

    @patch("connect.billing.get_gateway")
    @patch("connect.common.models.Project.create_flows")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_classifier")
    @patch("connect.common.models.Organization.get_ai_access_token")
    @patch("connect.authentication.models.User.send_request_flow_user_info")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_template_project")
    def test_create_organization_lead_project_fail_create_flows(
        self, flows_info, send_request_flow_user_info, get_ai_access_token,
        create_classifier, create_flows, mock_get_gateway
    ):
        mock_get_gateway.return_value = StripeMockGateway()
        flows_info.side_effect = [{"data": '{"id": 1, "uuid": "6b6a8c8b-6734-4110-81c9-287eaeab8e26"}'}]
        send_request_flow_user_info.side_effect = [True]
        get_ai_access_token.side_effect = [(True, str(uuid.uuid4()))]
        create_classifier.side_effect = [{"status": 201, "data": {"uuid": "fdd4a7bb-fe5a-41b1-96a2-96d95c4e7aab"}}]
        response_data = {
            "data": {"message": "Could not create flow"},
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
        self.assertEquals(content_data, response_data.get("data"))

    @patch("connect.billing.get_gateway")
    @patch("connect.common.models.Project.whatsapp_demo_integration")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_flows")
    @patch("connect.api.v1.internal.chats.chats_rest_client.ChatsRESTClient.create_chat_project")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_classifier")
    @patch("connect.common.models.Organization.get_ai_access_token")
    @patch("connect.authentication.models.User.send_request_flow_user_info")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_template_project")
    def test_create_organization_lead_project_fail_integrate_wpp(
        self, flows_info, send_request_flow_user_info, get_ai_access_token,
        create_classifier, create_chat_project, create_flows,
        wpp_integration, mock_get_gateway
    ):
        mock_get_gateway.return_value = StripeMockGateway()
        response_data = {
            "data": {"message": "Could not create flow"},
            "status": status.HTTP_500_INTERNAL_SERVER_ERROR
        }

        flows_info.side_effect = [{"data": '{"id": 1, "uuid": "6b6a8c8b-6734-4110-81c9-287eaeab8e26"}'}]
        send_request_flow_user_info.side_effect = [True]
        get_ai_access_token.side_effect = [(True, str(uuid.uuid4()))]
        create_classifier.side_effect = [{"status": 201, "data": {"uuid": "fdd4a7bb-fe5a-41b1-96a2-96d95c4e7aab"}}]
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
        self.assertEquals(content_data, response_data.get("data"))

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

    @patch("connect.billing.get_gateway")
    @patch("connect.api.v1.internal.integrations.integrations_rest_client.IntegrationsRESTClient.whatsapp_demo_integration")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_flows")
    @patch("connect.api.v1.internal.chats.chats_rest_client.ChatsRESTClient.create_chat_project")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_classifier")
    @patch("connect.api.v1.internal.intelligence.intelligence_rest_client.IntelligenceRESTClient.get_access_token")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_globals")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_template_project")
    @patch("connect.api.v1.internal.intelligence.intelligence_rest_client.IntelligenceRESTClient.create_organization")
    def test_create_organization_financial(
        self,
        create_organization,
        create_template_project,
        create_globals,
        get_access_token,
        create_classifier,
        create_chat_project,
        create_flows,
        whatsapp_demo_integration,
        mock_get_gateway
    ):

        mock_get_gateway.return_value = StripeMockGateway()

        class GlobalResponse:
            status_code = 201

            @staticmethod
            def json():
                return {
                    "org": "75694862-7dee-411f-a2d1-8a48fad743d2",
                    "name": "appkey",
                    "value": "1234567"
                }

        chats_data = {
            "ticketer": {"uuid": str(uuid.uuid4()), "name": "Test Ticketer"},
            "queue": {"uuid": str(uuid.uuid4()), "name": "Test Queue"},
        }

        class ChatsResponse:
            text = json.dumps(chats_data)

        flows_response = '{"uuid": "9785a273-37de-4658-bfa2-d8028dc06c84"}'

        wpp_data = {
            "redirect_url": "https://example.com",
            "router_token": "rt_token"
        }

        # side effects

        create_organization.side_effect = [{"id": 1}]
        create_template_project.side_effect = [{"data": '{"id": 1, "uuid": "6b6a8c8b-6734-4110-81c9-287eaeab8e26"}'}]
        create_globals.side_effect = [GlobalResponse]
        get_access_token.side_effect = ["6b6a8c8b-6734-tokn-81c9-287eaeab8e26"]
        create_classifier.side_effect = [{"status": 201, "data": {"uuid": "fdd4a7bb-fe5a-41b1-96a2-96d95c4e7aab"}}]
        create_chat_project.side_effect = [ChatsResponse()]
        create_flows.side_effect = [dict(status=201, data=flows_response)]
        whatsapp_demo_integration.side_effect = [wpp_data]

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
            "template_type": Project.TYPE_OMIE_PAYMENT_FINANCIAL_CHAT_GPT,
            "globals": {
                "appkey": 1234567890,
                "appsecret": "0abcdefghjkl",
            }
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

    @patch("connect.billing.get_gateway")
    @patch("connect.api.v1.internal.integrations.integrations_rest_client.IntegrationsRESTClient.whatsapp_demo_integration")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_flows")
    @patch("connect.api.v1.internal.chats.chats_rest_client.ChatsRESTClient.create_chat_project")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_classifier")
    @patch("connect.api.v1.internal.intelligence.intelligence_rest_client.IntelligenceRESTClient.get_access_token")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_globals")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.update_user_permission_project")
    @patch("connect.api.v1.internal.integrations.integrations_rest_client.IntegrationsRESTClient.update_user_permission_project")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_template_project")
    @patch("connect.api.v1.internal.intelligence.intelligence_rest_client.IntelligenceRESTClient.create_organization")
    def test_create_organization_omie_lead_capture(
        self,
        create_organization,
        create_template_project,
        integrations_perm,
        flows_perm,
        create_globals,
        get_access_token,
        create_classifier,
        create_chat_project,
        create_flows,
        whatsapp_demo_integration,
        mock_get_gateway
    ):
        mock_get_gateway.return_value = StripeMockGateway()
        integrations_perm.side_effect = [200, 200]
        flows_perm.side_effect = [200, 200]

        class GlobalResponse:
            status_code = 201

            @staticmethod
            def json():
                return {
                    "org": "75694862-7dee-411f-a2d1-8a48fad743d2",
                    "name": "appkey",
                    "value": "1234567"
                }

        chats_data = {
            "ticketer": {"uuid": str(uuid.uuid4()), "name": "Test Ticketer"},
            "queue": {"uuid": str(uuid.uuid4()), "name": "Test Queue"},
        }

        class ChatsResponse:
            text = json.dumps(chats_data)

        flows_response = '{"uuid": "9785a273-37de-4658-bfa2-d8028dc06c84"}'

        wpp_data = {
            "redirect_url": "https://example.com",
            "router_token": "rt_token"
        }

        # side effects

        create_organization.side_effect = [{"id": 1}]
        create_template_project.side_effect = [{"data": '{"id": 1, "uuid": "6b6a8c8b-6734-4110-81c9-287eaeab8e26"}'}]
        create_globals.side_effect = [GlobalResponse]
        get_access_token.side_effect = ["6b6a8c8b-6734-tokn-81c9-287eaeab8e26"]
        create_classifier.side_effect = [{"status": 201, "data": {"uuid": "fdd4a7bb-fe5a-41b1-96a2-96d95c4e7aab"}}]
        create_chat_project.side_effect = [ChatsResponse()]
        create_flows.side_effect = [dict(status=201, data=flows_response)]
        whatsapp_demo_integration.side_effect = [wpp_data]

        org_data = {
            "name": "OMIE LEAD CAPTURE",
            "description": "OMIE LEAD CAPTURE",
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
            "template_type": Project.TYPE_OMIE_LEAD_CAPTURE,
            "globals": {
                "appkey": 1234567890,
                "appsecret": "0abcdefghjkl",
                "codigo_da_conta": "-- 1 --",
                "codigo_da_origem": "-- 1 --",
                "codigo_da_solucao": "-- 2 --",
                "codigo_do_vendedor": "-- 2 --",
            }
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

        # print(content_data)

        organization = content_data.get("organization")

        self.assertEquals(response.status_code, status.HTTP_201_CREATED)
        self.assertEquals(organization["authorizations"]["count"], 2)

    @patch("connect.api.v1.internal.intelligence.intelligence_rest_client.IntelligenceRESTClient.create_organization")
    @patch("connect.authentication.models.User.send_request_flow_user_info")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_project")
    def test_user_email_setup(self, create_project, send_request_flow_user_info, create_organization):
        UserEmailSetup.objects.create(user=self.user, receive_project_emails=False, receive_organization_emails=False)
        intelligence_organization = 555
        create_project.side_effect = [{"id": 1, "uuid": uuid.uuid4()}]
        create_organization.side_effect = [{"id": intelligence_organization}]
        send_request_flow_user_info.side_effect = [True]
        org_data = {
            "name": "Email Setup",
            "description": "Email Setup",
            "organization_billing_plan": BillingPlan.PLAN_TRIAL,
            "authorizations": [
                {"user_email": "e@mail.com", "role": 3},
                {"user_email": "user_1@user.com", "role": 3}
            ],
        }

        project_data = {
            "date_format": "D",
            "name": "Email Setup",
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


class OrganizationTestCase(TestCase):
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway):
        mock_get_gateway.return_value = StripeMockGateway()
        self.factory = APIRequestFactory()
        self.user, self.user_token = create_user_and_token("user")

        self.org = Organization.objects.create(
            name="V2 Org 1",
            description="V2 Org 1",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )

        self.auth = self.org.authorizations.create(
            user=self.user, role=OrganizationRole.ADMIN.value
        )

    @patch("connect.api.v1.internal.intelligence.intelligence_rest_client.IntelligenceRESTClient.create_organization")
    def test_create_ai_organization(self, create_organization):
        intelligence_organization = 555
        create_organization.side_effect = [{"id": intelligence_organization}]
        organization = self.org
        created, data = organization.create_ai_organization(self.auth.user.email)
        self.assertTrue(created)
        self.assertEquals(intelligence_organization, data)

    @patch("connect.api.v1.internal.intelligence.intelligence_rest_client.IntelligenceRESTClient.create_organization")
    def test_error_create_ai_organization(self, create_organization):
        organization = self.org
        create_organization.side_effect = [Exception("Error")]
        created, data = organization.create_ai_organization(self.auth.user.email)
        self.assertFalse(created)
        self.assertEquals(data.get("status"), status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEquals(data.get("data").get("message"), "Could not create organization in AI module")


class OrganizationAuthorizationTestCase(TestCase):

    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway):
        mock_get_gateway.return_value = StripeMockGateway()

        self.owner, self.owner_token = create_user_and_token("owner")
        self.org1 = Organization.objects.create(
            name="Test project methods",
            description="",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__payment_method=BillingPlan.PAYMENT_METHOD_CREDIT_CARD,
            organization_billing__plan=BillingPlan.PLAN_ENTERPRISE,
        )
        self.organization_authorization = self.org1.authorizations.create(
            user=self.owner, role=OrganizationRole.ADMIN.value
        )

    def test_list_project_authorizations(self):
        organization = self.org1
        url = f"/v2/organizations/{organization.uuid}/list-organization-authorizations"
        response = self.client.get(url, HTTP_AUTHORIZATION=f"Token {self.owner_token}")
        self.assertEquals(response.status_code, status.HTTP_200_OK)


class CustomCountTestCase(TestCase):
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway) -> None:
        mock_get_gateway.return_value = StripeMockGateway()

        self.owner, self.owner_token = create_user_and_token("owner")
        self.org1 = Organization.objects.create(
            name="Test project methods",
            description="",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__payment_method=BillingPlan.PAYMENT_METHOD_CREDIT_CARD,
            organization_billing__plan=BillingPlan.PLAN_ENTERPRISE,
        )
        self.project = self.org1.project.create(name="test case")
        self.organization_authorization = self.org1.authorizations.create(
            user=self.owner, role=OrganizationRole.ADMIN.value
        )

    def test_view(self):
        from freezegun import freeze_time
        # too many loops
        start = pendulum.now().start_of("month")
        end = start.end_of("month")
        period = end - start
        ran = period.range("days")

        for day in ran:
            freezer = freeze_time(day)
            freezer.start()
            create_contacts(num_contacts=10, day=day)
            daily_contact_count()
            freezer.stop()

        organization = self.org1
        url = f"/v2/organizations/{organization.uuid}/get_contact_active?before={end.date()}&after={start.date()}"
        response = self.client.get(url, HTTP_AUTHORIZATION=f"Token {self.owner_token}", follow=True)
        self.assertEquals(response.status_code, status.HTTP_200_OK)
