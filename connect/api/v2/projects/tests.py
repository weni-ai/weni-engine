import json
import uuid
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from django.test import TestCase
from unittest.mock import Mock, patch

from connect.api.v1.tests.utils import create_user_and_token
from connect.common.models import Organization, BillingPlan, OrganizationRole, Project
from connect.api.v2.projects.views import ProjectViewSet
from connect.common.mocks import StripeMockGateway

from connect.api.v1.internal.flows.flows_rest_client import FlowsRESTClient


class ProjectViewSetTestCase(TestCase):
    @patch("connect.common.signals.update_user_permission_project")
    @patch("connect.billing.get_gateway")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.update_user_permission_project")
    @patch("connect.api.v1.internal.integrations.integrations_rest_client.IntegrationsRESTClient.update_user_permission_project")
    def setUp(self, integrations_rest, flows_rest, mock_get_gateway, mock_permission):
        integrations_rest.side_effect = [200, 200]
        flows_rest.side_effect = [200, 200]
        mock_get_gateway.return_value = StripeMockGateway()
        mock_permission.return_value = True
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

    @patch("connect.common.signals.update_user_permission_project")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.update_user_permission_project")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_project")
    def test_create_blank_project(self, create_project, update_user_permission_project, mock_permission):
        create_project.side_effect = [{"id": 1, "flow_organization": str(uuid.uuid4())}]
        update_user_permission_project.side_effect = [
            dict(status=status.HTTP_201_CREATED, data={}),

        ]
        mock_permission.return_value = True
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

    # @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_classifier")
    # @patch("connect.api.v1.internal.integrations.integrations_rest_client.IntegrationsRESTClient.whatsapp_demo_integration")
    # @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_flows")
    # @patch("connect.api.v1.internal.intelligence.intelligence_rest_client.IntelligenceRESTClient.get_access_token")
    # @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.update_user_permission_project")
    # @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_template_project")
    @patch("connect.common.signals.update_user_permission_project")
    @patch("connect.api.v1.internal.integrations.integrations_rest_client.IntegrationsRESTClient.whatsapp_demo_integration")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_flows")
    @patch("connect.api.v1.internal.chats.chats_rest_client.ChatsRESTClient.create_chat_project")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_classifier")
    @patch("connect.api.v1.internal.intelligence.intelligence_rest_client.IntelligenceRESTClient.get_access_token")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_globals")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.update_user_permission_project")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_template_project")
    def test_create_omie_project(self, create_template_project, update_user_permission_project, create_globals, get_access_token, create_classifier, create_chat_project, create_flows, whatsapp_demo_integration, mock_permission):
        class GlobalResponse:
            status_code = 201

            @staticmethod
            def json():
                return {
                    "org": "75694862-7dee-411f-a2d1-8a48fad743d2",
                    "name": "appkey",
                    "value": "1234567"
                }
        wpp_data = {
            "redirect_url": "https://example.com",
            "router_token": "rt_token"
        }
        mock_permission.return_value = True
        update_user_permission_project.side_effect = [
            dict(status=status.HTTP_201_CREATED, data={}),
            dict(status=status.HTTP_201_CREATED, data={}),
        ]

        class ChatsResponse:

            chats_data = {
                "ticketer": {"uuid": str(uuid.uuid4()), "name": "Test Ticketer"},
                "queue": {"uuid": str(uuid.uuid4()), "name": "Test Queue"},
            }

            @property
            def text(self):
                return json.dumps(self.chats_data)

        flows_response = '{"uuid": "9785a273-37de-4658-bfa2-d8028dc06c84"}'
        organization_uuid = str(self.org_1.uuid)

        create_template_project.side_effect = [{"data": '{"id": 1, "uuid": "6b6a8c8b-6734-4110-81c9-287eaeab8e26"}'}]
        create_globals.side_effect = [GlobalResponse]
        get_access_token.side_effect = ["6b6a8c8b-6734-tokn-81c9-287eaeab8e26"]
        create_classifier.side_effect = [{"status": 201, "data": {"uuid": "fdd4a7bb-fe5a-41b1-96a2-96d95c4e7aab"}}]
        create_chat_project.side_effect = [ChatsResponse()]
        create_flows.side_effect = [dict(status=201, data=flows_response)]
        whatsapp_demo_integration.side_effect = [wpp_data]

        body = {
            "date_format": "D",
            "name": "Test Omie",
            "timezone": "America/Argentina/Buenos_Aires",
            "template": True,
            "template_type": "omie"
        }
        path = f"/v2/organizations/{organization_uuid}projects/"
        method = {"post": "create"}
        user = self.user

        response, content_data = self.request(
            path,
            method,
            user=user,
            pk=organization_uuid,
            data=body
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
            "timezone": "America/Argentina/Buenos_Aires"
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
        self.assertEquals("America/Argentina/Buenos_Aires", content_data.get("timezone"))
        self.assertEquals(response.status_code, status.HTTP_200_OK)

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

    @patch("connect.common.signals.update_user_permission_project")
    @patch("connect.api.v1.internal.integrations.integrations_rest_client.IntegrationsRESTClient.whatsapp_demo_integration")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_flows")
    @patch("connect.api.v1.internal.chats.chats_rest_client.ChatsRESTClient.create_chat_project")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_classifier")
    @patch("connect.api.v1.internal.intelligence.intelligence_rest_client.IntelligenceRESTClient.get_access_token")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_globals")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.update_user_permission_project")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_template_project")
    def test_create_omie_financial_project(self, create_template_project, update_user_permission_project, create_globals, get_access_token, create_classifier, create_chat_project, create_flows, whatsapp_demo_integration, mock_permission):
        class GlobalResponse:
            status_code = 201

            @staticmethod
            def json():
                return {
                    "org": "75694862-7dee-411f-a2d1-8a48fad743d2",
                    "name": "appkey",
                    "value": "1234567"
                }
        wpp_data = {
            "redirect_url": "https://example.com",
            "router_token": "rt_token"
        }

        update_user_permission_project.side_effect = [
            dict(status=status.HTTP_201_CREATED, data={}),
            dict(status=status.HTTP_201_CREATED, data={}),
        ]
        mock_permission.return_value = True

        class ChatsResponse:
            chats_data = {
                "ticketer": {"uuid": str(uuid.uuid4()), "name": "Test Ticketer"},
                "queue": {"uuid": str(uuid.uuid4()), "name": "Test Queue"},
            }

            @property
            def text(self):
                return json.dumps(self.chats_data)

        flows_response = '{"uuid": "9785a273-37de-4658-bfa2-d8028dc06c84"}'

        create_template_project.side_effect = [{"data": '{"id": 1, "uuid": "6b6a8c8b-6734-4110-81c9-287eaeab8e26"}'}]
        create_globals.side_effect = [GlobalResponse]
        get_access_token.side_effect = ["6b6a8c8b-6734-tokn-81c9-287eaeab8e26"]
        create_classifier.side_effect = [{"status": 201, "data": {"uuid": "fdd4a7bb-fe5a-41b1-96a2-96d95c4e7aab"}}]
        create_chat_project.side_effect = [ChatsResponse()]
        create_flows.side_effect = [dict(status=201, data=flows_response)]
        whatsapp_demo_integration.side_effect = [wpp_data]

        organization_uuid = str(self.org_1.uuid)
        body = {
            "name": "ominho 2",
            "organization": organization_uuid,
            "date_format": "D",
            "timezone": "America/Argentina/Buenos_Aires",
            "template": True,
            "template_type": "omie_financial",
            "globals": {
                "appkey": "asdasdas",
                "appsecret": "asdasdas"
            }
        }
        path = f"/v2/organizations/{organization_uuid}projects/"
        method = {"post": "create"}
        user = self.user

        response, content_data = self.request(
            path,
            method,
            user=user,
            pk=organization_uuid,
            data=body
        )

        self.assertEquals(response.status_code, status.HTTP_201_CREATED)

    @patch("connect.common.signals.update_user_permission_project")
    @patch("connect.api.v1.internal.integrations.integrations_rest_client.IntegrationsRESTClient.whatsapp_demo_integration")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_flows")
    @patch("connect.api.v1.internal.chats.chats_rest_client.ChatsRESTClient.create_chat_project")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_classifier")
    @patch("connect.api.v1.internal.intelligence.intelligence_rest_client.IntelligenceRESTClient.get_access_token")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_globals")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.update_user_permission_project")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_template_project")
    def test_create_sac_chatgpt_project(self, create_template_project, update_user_permission_project, create_globals, get_access_token, create_classifier, create_chat_project, create_flows, whatsapp_demo_integration, mock_permission):
        class GlobalResponse:
            status_code = 201

            @staticmethod
            def json():
                return {
                    "org": "75694862-7dee-411f-a2d1-8a48fad743d2",
                    "name": "appkey",
                    "value": "1234567"
                }
        wpp_data = {
            "redirect_url": "https://example.com",
            "router_token": "rt_token"
        }

        update_user_permission_project.side_effect = [
            dict(status=status.HTTP_201_CREATED, data={}),
            dict(status=status.HTTP_201_CREATED, data={}),
        ]
        mock_permission.return_value = True

        class ChatsResponse:
            chats_data = {
                "ticketer": {"uuid": str(uuid.uuid4()), "name": "Test Ticketer"},
                "queue": {"uuid": str(uuid.uuid4()), "name": "Test Queue"},
            }

            @property
            def text(self):
                return json.dumps(self.chats_data)

        flows_response = '{"uuid": "9785a273-37de-4658-bfa2-d8028dc06c84"}'

        create_template_project.side_effect = [{"data": '{"id": 1, "uuid": "6b6a8c8b-6734-4110-81c9-287eaeab8e26"}'}]
        create_globals.side_effect = [GlobalResponse]
        get_access_token.side_effect = ["6b6a8c8b-6734-tokn-81c9-287eaeab8e26"]
        create_classifier.side_effect = [{"status": 201, "data": {"uuid": "fdd4a7bb-fe5a-41b1-96a2-96d95c4e7aab"}}]
        create_chat_project.side_effect = [ChatsResponse()]
        create_flows.side_effect = [dict(status=201, data=flows_response)]
        whatsapp_demo_integration.side_effect = [wpp_data]

        organization_uuid = str(self.org_1.uuid)
        body = {
            "name": "sac chatgpt",
            "organization": organization_uuid,
            "date_format": "D",
            "timezone": "America/Argentina/Buenos_Aires",
            "template": True,
            "template_type": "sac+chatgpt",
            "globals": {
                "chatgpt_token": "asdasdas",
                "Conteudo": "@globals.conteudo",
                "Personalidade": "@globals.personalidade",
                "Principios Seguranca": "@globals.principios_seguranca",
            }
        }
        path = f"/v2/organizations/{organization_uuid}/projects/"
        method = {"post": "create"}
        user = self.user

        response, content_data = self.request(
            path,
            method,
            user=user,
            pk=organization_uuid,
            data=body
        )

        self.assertEquals(response.status_code, status.HTTP_201_CREATED)

    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.update_project")
    def test_update_flows_project(self, mock_update_project):

        mock_response = Mock()
        mock_response.status_code = status.HTTP_200_OK
        mock_response.json.return_value = {"message": "Success"}

        mock_update_project.return_value = mock_response

        organization_uuid = str(self.org_1.uuid)
        project_uuid = str(self.project1.uuid)

        url = f"v2/organizations/{organization_uuid}/projects/{project_uuid}/"
        data = {
            "name": "Novo nome",
            "timezone": "America/New_York",
            "date_format": "D",
        }
        method = {"patch": "partial_update"}
        response, content_data = self.request(url, method, data, user=self.user, pk=organization_uuid, project_uuid=project_uuid)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(content_data.get("name"), data.get("name"))
        mock_update_project.assert_called_once_with(project_uuid, name="Novo nome", timezone="America/New_York", date_format="D")


class ProjectTestCase(TestCase):

    @patch("connect.common.signals.update_user_permission_project")
    @patch("connect.billing.get_gateway")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.update_user_permission_project")
    def setUp(self, update_user_permission_project, mock_get_gateway, mock_permissions):
        mock_get_gateway.return_value = StripeMockGateway()
        mock_permissions.return_value = True
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
        create_classifier.side_effect = [{"data": {"uuid": response_data}, "status": status.HTTP_201_CREATED}]

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

    @patch("requests.post")
    def test_create_flows_json(self, post):
        flows = FlowsRESTClient()
        project_uuid = uuid.uuid4()
        classifier_uuid = uuid.uuid4()
        template_type = "omie"
        flows.create_flows(project_uuid, classifier_uuid, template_type)


class ProjectAuthorizationTestCase(TestCase):

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
        self.project1 = self.org1.project.create(
            name="Project 1",
            timezone="America/Sao_Paulo",
            flow_organization=uuid.uuid4(),
        )

    def test_list_project_authorizations(self):
        project = self.project1
        url = f"/v2/projects/{project.uuid}/list-project-authorizations"
        response = self.client.get(url, HTTP_AUTHORIZATION=f"Token {self.owner_token}")
        users_list = response.data['authorizations']['users']
        users_count = len(users_list)
        self.assertEquals(response.status_code, status.HTTP_200_OK)
        self.assertEquals(users_count, 1)
