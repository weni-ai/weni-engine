import json
import uuid
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from django.test import TestCase
from unittest.mock import patch

from connect.api.v1.tests.utils import create_user_and_token
from connect.common.models import Organization, BillingPlan, OrganizationRole, Project
from connect.api.v2.projects.views import ProjectViewSet


class ProjectViewSetTestCase(TestCase):
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.update_user_permission_project")
    @patch("connect.api.v1.internal.integrations.integrations_rest_client.IntegrationsRESTClient.update_user_permission_project")
    def setUp(self, integrations_rest, flows_rest):
        integrations_rest.side_effect = [200, 200]
        flows_rest.side_effect = [200, 200]

        self.factory = APIRequestFactory()
        self.user, self.user_token = create_user_and_token("user")

        self.org_1 = Organization.objects.create(
            name="V2 Org 1",
            description="V2 Org 1",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )

        self.project1 = Project.objects.create(
            name="V2 Project 1",
            flow_organization=uuid.uuid4(),
            organization=self.org_1
        )

        self.project2 = Project.objects.create(
            name="V2 Project 2",
            flow_organization=uuid.uuid4(),
            organization=self.org_1
        )

        self.org_auth_1 = self.org_1.authorizations.create(
            user=self.user, role=OrganizationRole.ADMIN.value
        )

    def make_request(self, path: str, method: dict, data: dict = None):
        for key in method:
            if key == "post":
                request = self.factory.post(path, data, format="json")
            elif key == "delete":
                request = self.factory.delete(path)
            elif key == "patch":
                request = self.factory.patch(path, data, format="json")
            else:
                request = self.factory.get(path)
            return request

    def request(self, path: str, method: dict, data: dict = None, user=None, **kwargs):
        pk = kwargs.get("pk")
        project_uuid = kwargs.get("project_uuid")
        content_data = ""

        request = self.make_request(path, method, data)
        force_authenticate(request, user=user, token=user.auth_token)

        response = ProjectViewSet.as_view(method)(request, organization_uuid=pk, data=data, uuid=project_uuid)
        response.render()

        if not response.status_code == status.HTTP_204_NO_CONTENT:
            content_data = json.loads(response.content)
        return response, content_data

    def test_retrieve_project(self):
        organization_uuid = str(self.org_1.uuid)
        project_uuid = str(self.project1.uuid)

        path = f"/v2/organizations/{organization_uuid}projects/{project_uuid}"
        method = {"get": "retrieve"}
        user = self.user

        response, content_data = self.request(
            path,
            method,
            user=user,
            pk=organization_uuid,
            project_uuid=project_uuid
        )

        self.assertEquals(response.status_code, status.HTTP_200_OK)
        self.assertEquals(content_data.get("uuid"), project_uuid)

    def test_list_project(self):
        organization_uuid = str(self.org_1.uuid)

        path = f"/v2/organizations/{organization_uuid}projects/"
        method = {"get": "list"}
        user = self.user

        response, content_data = self.request(
            path,
            method,
            user=user,
            pk=organization_uuid,
        )

        self.assertEquals(response.status_code, status.HTTP_200_OK)
        self.assertEquals(content_data["count"], 2)

    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_project")
    def test_create_blank_project(self, create_project):
        create_project.side_effect = [{"id": 1, "uuid": str(uuid.uuid4())}]
        organization_uuid = str(self.org_1.uuid)
        data = {
            "date_format": "D",
            "name": "Test V2 Project",
            "timezone": "America/Argentina/Buenos_Aires",
        }
        path = f"/v2/organizations/{organization_uuid}projects/"
        method = {"post": "create"}
        user = self.user

        response, content_data = self.request(
            path,
            method,
            user=user,
            pk=organization_uuid,
            data=data
        )
        Project.objects.get(uuid=content_data.get("uuid"))
        self.assertEquals(response.status_code, status.HTTP_201_CREATED)

    @patch("connect.api.v1.internal.chats.chats_rest_client.ChatsRESTClient.update_chats_project")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.update_project")
    def test_update_project(self, flows_update_project, update_chats_project):
        flows_update_project.side_effect = [200]
        update_chats_project.side_effect = [200]

        organization_uuid = str(self.org_1.uuid)
        project_uuid = str(self.project1.uuid)
        data = {
            "name": "Test V2 Project (update)",
        }
        path = f"/v2/organizations/{organization_uuid}projects/{project_uuid}"
        method = {"patch": "update"}
        user = self.user

        response, content_data = self.request(
            path,
            method,
            user=user,
            pk=organization_uuid,
            project_uuid=project_uuid,
            data=data
        )
        # Project.objects.get(uuid=content_data.get("uuid"))
        # self.assertEquals(response.status_code, status.HTTP_200_OK)

    @patch("connect.api.v1.internal.intelligence.intelligence_rest_client.IntelligenceRESTClient.get_organization_intelligences")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.get_project_flows")
    def test_project_search(self, flows_result, intelligence_result):
        intelligence_result.side_effect = [{"count": 1, "next": None, "previous": None, "results": []}]
        flows_result.side_effect = [{"count": 1, "next": None, "previous": None, "results": []}]

        organization_uuid = str(self.org_1.uuid)
        project_uuid = str(self.project1.uuid)

        path = f"/v2/organizations/{organization_uuid}/projects/{project_uuid}/search-project/?text=SearchText"
        method = {"get": "project_search"}
        user = self.user

        response, content_data = self.request(
            path,
            method,
            user=user,
            pk=organization_uuid,
            project_uuid=project_uuid
        )

        self.assertEquals(response.status_code, status.HTTP_200_OK)

    def test_update_last_opened_on(self):
        organization_uuid = str(self.org_1.uuid)
        project_uuid = str(self.project1.uuid)

        path = f"/v2/organizations/{organization_uuid}/projects/{project_uuid}/update_last_opened_on"
        method = {"post": "update_last_opened_on"}
        user = self.user

        response, content_data = self.request(
            path,
            method,
            user=user,
            pk=organization_uuid,
            project_uuid=project_uuid
        )

        self.assertEquals(response.status_code, status.HTTP_200_OK)

    def test_destroy_project(self):
        organization_uuid = str(self.org_1.uuid)
        project_uuid = str(self.project1.uuid)

        path = f"/v2/organizations/{organization_uuid}/projects/{project_uuid}/"
        method = {"delete": "destroy"}
        user = self.user

        response, content_data = self.request(
            path,
            method,
            user=user,
            pk=organization_uuid,
            project_uuid=project_uuid
        )

        self.assertEquals(response.status_code, status.HTTP_204_NO_CONTENT)


class ProjectTestCase(TestCase):
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.update_user_permission_project")
    def setUp(self, update_user_permission_project):
        update_user_permission_project.side_effect = [True]
        self.organization = Organization.objects.create(
            name="Test project methods",
            description="",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__payment_method=BillingPlan.PAYMENT_METHOD_CREDIT_CARD,
            organization_billing__plan=BillingPlan.PLAN_ENTERPRISE,
        )
        self.user, self.user_token = create_user_and_token("user")
        self.organization_authorization = self.organization.authorizations.create(
            user=self.user, role=OrganizationRole.ADMIN.value
        )

        self.project = self.organization.project.create(
            name="project test methods",
            timezone="America/Sao_Paulo",
            flow_organization=uuid.uuid4(),
            is_template=True,
            template_type=Project.TYPE_SUPPORT,
            created_by=self.user
        )

    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_classifier")
    def test_create_classifier(self, create_classifier):
        response_data = uuid.uuid4()
        create_classifier.side_effect = [{"data": {"uuid": response_data}}]

        project = self.project
        authorization = project.get_user_authorization(self.user)
        access_token = uuid.uuid4()

        created, data = self.project.create_classifier(authorization, project.template_type, access_token)

        self.assertTrue(created)
        self.assertEquals(data, response_data)

    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_classifier")
    def test_error_create_classifier(self, create_classifier):
        create_classifier.side_effect = [Exception("Error")]

        project = self.project
        authorization = project.get_user_authorization(self.user)
        access_token = uuid.uuid4()

        created, data = self.project.create_classifier(authorization, project.template_type, access_token)

        self.assertFalse(created)
        self.assertEquals(data.get("status"), status.HTTP_500_INTERNAL_SERVER_ERROR)

    @patch("connect.api.v1.internal.chats.chats_rest_client.ChatsRESTClient.create_chat_project")
    def test_create_chats_project(self, create_chat_project):
        ticketer = uuid.uuid4()

        class Response:
            text = json.dumps({"ticketer": str(ticketer), "queue": "default"})

        chats_response = Response()
        create_chat_project.side_effect = [chats_response]
        project = self.project
        created, data = project.create_chats_project()
        self.assertTrue(created)

    @patch("connect.api.v1.internal.chats.chats_rest_client.ChatsRESTClient.create_chat_project")
    def test_error_create_chats_project(self, create_chat_project):
        create_chat_project.side_effect = [Exception("Error")]
        created, data = self.project.create_chats_project()
        self.assertFalse(created)
        self.assertEquals(data.get("status"), status.HTTP_500_INTERNAL_SERVER_ERROR)

    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_flows")
    @patch("connect.api.v1.internal.chats.chats_rest_client.ChatsRESTClient.create_chat_project")
    def test_create_flows(self, create_chat_project, create_flows):
        data = {
            "ticketer": {"uuid": str(uuid.uuid4()), "name": "Test Ticketer"},
            "queue": {"uuid": str(uuid.uuid4()), "name": "Test Queue"},
        }

        class Response:
            text = json.dumps(data)

        flows_response = '{"uuid": "9785a273-37de-4658-bfa2-d8028dc06c84"}'
        create_chat_project.side_effect = [Response()]

        create_flows.side_effect = [dict(status=201, data=flows_response)]
        classifier_uuid = uuid.uuid4()
        project = self.project
        created, data = project.create_flows(classifier_uuid)
        self.assertTrue(created)

    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_flows")
    @patch("connect.api.v1.internal.chats.chats_rest_client.ChatsRESTClient.create_chat_project")
    def test_error_create_flows(self, create_chat_project, create_flows):
        data = {
            "ticketer": {"uuid": str(uuid.uuid4()), "name": "Test Ticketer"},
            "queue": {"uuid": str(uuid.uuid4()), "name": "Test Queue"},
        }

        class Response:
            text = json.dumps(data)

        create_chat_project.side_effect = [Response()]
        create_flows.side_effect = [Exception()]
        classifier_uuid = uuid.uuid4()
        project = self.project
        created, data = project.create_flows(classifier_uuid)
        self.assertFalse(created)

    @patch("connect.api.v1.internal.integrations.integrations_rest_client.IntegrationsRESTClient.whatsapp_demo_integration")
    def test_whatsapp_demo_integration(self, wpp_integration):
        data = {
            "redirect_url": "https://example.com",
            "router_token": "rt_token"
        }
        wpp_integration.side_effect = [data]
        project = self.project
        token = "token"
        created, response_data = project.whatsapp_demo_integration(token)
        self.assertTrue(created)
        self.assertEquals(data, response_data)

    @patch("connect.api.v1.internal.integrations.integrations_rest_client.IntegrationsRESTClient.whatsapp_demo_integration")
    def test_error_whatsapp_demo_integration(self, wpp_integration):
        wpp_integration.side_effect = [Exception("Error")]
        project = self.project
        token = "token"
        created, response_data = project.whatsapp_demo_integration(token)
        self.assertFalse(created)
