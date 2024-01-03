import json
import uuid as uuid4
from unittest.mock import patch
from unittest import skipIf
from django.test import RequestFactory
from django.test import TestCase
from django.test.client import MULTIPART_CONTENT
from rest_framework import status

from connect.api.v1.project.views import ProjectViewSet, TemplateProjectViewSet
from connect.api.v1.tests.utils import create_user_and_token
from connect.common.models import (
    Project,
    Organization,
    BillingPlan,
    OrganizationRole,
    RequestPermissionProject,
    RequestPermissionOrganization,
)
from connect.common.mocks import StripeMockGateway


@skipIf(True, "create project v1 is deprecated")
class CreateProjectAPITestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.owner, self.owner_token = create_user_and_token("owner")

        self.organization = Organization.objects.create(
            name="test organization",
            description="",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="free",
        )
        self.organization_authorization = self.organization.authorizations.create(
            user=self.owner, role=OrganizationRole.ADMIN.value
        )

    def request(self, data, token=None):
        authorization_header = (
            {"HTTP_AUTHORIZATION": "Token {}".format(token.key)} if token else {}
        )

        request = self.factory.post(
            "/v1/organization/project/", data, **authorization_header
        )

        response = ProjectViewSet.as_view({"post": "create"})(request)
        response.render()
        content_data = json.loads(response.content)
        return (response, content_data)

    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.create_project")
    def test_create_project(self, mock_create_project):
        project_uuid = str(uuid4.uuid4())
        mock_create_project.return_value = {"uuid": project_uuid}

        data = {
            "name": "Project 1",
            "timezone": "America/Sao_Paulo",
            "flow_organization": uuid4.uuid4(),
            "organization": str(self.organization.uuid),
        }
        response, content_data = self.request(data, self.owner_token)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        project = Project.objects.get(pk=content_data.get("uuid"))

        self.assertEqual(project.name, "Project 1")

        self.assertEqual(
            project.__str__(),
            f"{project.uuid} - Project: {project.name} - Org: {project.organization.name}",
        )


class ListProjectAPITestCase(TestCase):
    @patch("connect.common.signals.update_user_permission_project")
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway, mock_permission):
        mock_get_gateway.return_value = StripeMockGateway()
        mock_permission.return_value = True
        self.factory = RequestFactory()
        self.owner, self.owner_token = create_user_and_token("owner")
        self.user, self.user_token = create_user_and_token("user")
        self.financial, self.financial_token = create_user_and_token("financial")
        self.organization = Organization.objects.create(
            name="test organization",
            description="",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )

        RequestPermissionOrganization.objects.create(
            email=self.owner.email,
            organization=self.organization,
            role=OrganizationRole.ADMIN.value,
            created_by=self.owner
        )
        RequestPermissionOrganization.objects.create(
            email=self.user.email,
            organization=self.organization,
            role=OrganizationRole.CONTRIBUTOR.value,
            created_by=self.owner
        )
        RequestPermissionOrganization.objects.create(
            email=self.financial.email,
            organization=self.organization,
            role=OrganizationRole.FINANCIAL.value,
            created_by=self.owner
        )

        self.owner_organization_authorization = self.organization.authorizations.get(user=self.owner)
        self.user_organization_authorization = self.organization.authorizations.get(user=self.user)
        self.financial_organization_authorization = self.organization.authorizations.get(user=self.financial)

        self.project = self.organization.project.create(
            name="project test",
            timezone="America/Sao_Paulo",
            flow_organization=uuid4.uuid4(),
        )
        self.project2 = self.organization.project.create(
            name="project test 2",
            timezone="America/Sao_Paulo",
            flow_organization=uuid4.uuid4(),
        )

    def request(self, param, value, token=None):
        authorization_header = (
            {"HTTP_AUTHORIZATION": "Token {}".format(token.key)} if token else {}
        )

        request = self.factory.get(
            "/v1/organization/project/?{}={}".format(param, value),
            **authorization_header,
        )

        response = ProjectViewSet.as_view({"get": "list"})(
            request, project=self.project.uuid
        )
        response.render()
        content_data = json.loads(response.content)

        return (response, content_data)

    def test_user_project_authorizations(self):
        response, content_data = self.request(
            "organization",
            self.organization.uuid,
            self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(content_data.get("count"), 2)

    def test_owner_project_authorizations(self):
        response, content_data = self.request(
            "organization",
            self.organization.uuid,
            self.owner_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(content_data.get("count"), 2)

    def test_financial_project_authorizations(self):
        response, content_data = self.request(
            "organization",
            self.organization.uuid,
            self.financial_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(content_data.get("count"), 0)


class UpdateProjectTestCase(TestCase):
    @patch("connect.common.signals.update_user_permission_project")
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway, mock_permission):
        mock_get_gateway.return_value = StripeMockGateway()
        mock_permission.return_value = True
        self.factory = RequestFactory()

        self.owner, self.owner_token = create_user_and_token("owner")
        self.user, self.user_token = create_user_and_token("user")

        self.organization = Organization.objects.create(
            name="test organization",
            description="",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="free",
        )
        RequestPermissionOrganization.objects.create(
            email=self.owner.email,
            organization=self.organization,
            role=OrganizationRole.ADMIN.value,
            created_by=self.owner
        )
        self.organization_authorization = self.organization.authorizations.get(user=self.owner)
        self.project = self.organization.project.create(
            name="project test",
            timezone="America/Sao_Paulo",
            flow_organization=uuid4.uuid4(),
        )

    def request(self, project, data={}, token=None):
        authorization_header = (
            {"HTTP_AUTHORIZATION": "Token {}".format(token.key)} if token else {}
        )

        request = self.factory.patch(
            "/v1/org/project/{}/".format(project.uuid),
            self.factory._encode_data(data, MULTIPART_CONTENT),
            MULTIPART_CONTENT,
            **authorization_header,
        )

        response = ProjectViewSet.as_view({"patch": "update"})(
            request, uuid=project.uuid, partial=True
        )

        response.render()
        content_data = json.loads(response.content)
        return (response, content_data)

    @patch("connect.usecases.project.update_project.UpdateProjectUseCase.send_updated_project")
    def test_okay_update_name(
        self,
        mock_send_updated_project
    ):
        mock_send_updated_project.side_effect = [True]
        response, content_data = self.request(
            self.project,
            {"name": "Project new"},
            self.owner_token,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unauthorized(self):
        response, content_data = self.request(
            self.project,
            {"name": "Project new"},
            self.user_token,
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        user_authorization = self.organization.get_user_authorization(self.user)
        user_authorization.role = OrganizationRole.CONTRIBUTOR.value
        user_authorization.save(update_fields=["role"])

        response, content_data = self.request(
            self.project,
            {"name": "Project new"},
            self.user_token,
        )
        # if the user dosen't have an authorization he cant find the project
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class DeleteProjectAuthTestCase(TestCase):
    @patch("connect.common.signals.update_user_permission_project")
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway, mock_permission):
        mock_get_gateway.return_value = StripeMockGateway()
        mock_permission.return_value = True

        self.factory = RequestFactory()

        self.owner, self.owner_token = create_user_and_token("owner")
        self.user, self.user_token = create_user_and_token("user")

        self.organization = Organization.objects.create(
            name="test organization",
            description="",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="free",
        )
        self.organization_authorization = self.organization.authorizations.create(
            user=self.owner, role=OrganizationRole.ADMIN.value
        )
        self.project = self.organization.project.create(
            name="project test",
            timezone="America/Sao_Paulo",
            flow_organization=uuid4.uuid4(),
        )

        self.owner_project_authorization = self.project.get_user_authorization(self.owner)
        self.owner_project_authorization.role = 3
        self.owner_project_authorization.save()

        self.project_auth = self.project.get_user_authorization(self.user)
        self.project_auth.role = 3
        self.project_auth.save()

        self.request_auth = RequestPermissionProject.objects.create(
            project=self.project,
            email="delete@auth.com",
            role=2,
            created_by=self.owner)

    def request(self, project, data={}, token=None):
        authorization_header = (
            {"HTTP_AUTHORIZATION": "Token {}".format(token.key)} if token else {}
        )

        request = self.factory.delete(
            f"/v1/organization/project/grpc/destroy-user-permission/{project}/",
            data=json.dumps(data),
            content_type="application/json",
            format="json",
            **authorization_header,
        )

        response = ProjectViewSet.as_view({"delete": "destroy_user_permission"})(
            request, project_uuid=project)
        return response

    def test_destroy_permission_project(self):
        response = self.request(
            self.project.uuid,
            {"email": f"{self.user.email}"},
            self.owner_token,
        )
        self.assertEquals(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_destroy_request_permission_project(self):
        response = self.request(
            self.project.uuid,
            {"email": "delete@auth.com"},
            self.owner_token,
        )
        self.assertEquals(response.status_code, status.HTTP_204_NO_CONTENT)


# @skipIf(True, "Needs mock")
class TemplateProjectTestCase(TestCase):
    @patch("connect.common.signals.update_user_permission_project")
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway, mock_permission):
        mock_get_gateway.return_value = StripeMockGateway()
        mock_permission.return_value = True
        self.factory = RequestFactory()

        self.user, self.user_token = create_user_and_token("user")
        self.new_user, self.new_user_token = create_user_and_token("new_user")

        self.organization = Organization.objects.create(
            name="test organization",
            description="",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="enterprise",
        )
        self.organization_authorization = self.organization.authorizations.create(
            user=self.user, role=OrganizationRole.ADMIN.value
        )

        self.organization_authorization = self.organization.authorizations.create(
            user=self.new_user, role=OrganizationRole.ADMIN.value
        )

    def request(self, project=None, token=None):
        authorization_header = (
            {"HTTP_AUTHORIZATION": "Token {}".format(token.key)} if token else {}
        )
        if project:
            ...
        request = self.factory.get(
            "/v1/organization/template-project/",
            **authorization_header,
        )

        response = TemplateProjectViewSet.as_view({"get": "list"})(
            request)

        response.render()
        content_data = json.loads(response.content)

        return response, content_data

    def request_create(self, data, token=None):
        authorization_header = (
            {"HTTP_AUTHORIZATION": "Token {}".format(token.key)} if token else {}
        )
        request = self.factory.post(
            "/v1/organization/template-project/",
            data=json.dumps(data),
            content_type="application/json",
            format="json",
            **authorization_header,
        )

        response = TemplateProjectViewSet.as_view({"post": "create"})(
            request, data)
        response.render()
        content_data = json.loads(response.content)

        return response, content_data

    def test_get_template_projects(self):
        response, content_data = self.request(
            token=self.user_token,
        )
        self.assertEquals(response.status_code, status.HTTP_200_OK)

    def test_get_template_projects_new_user(self):
        response, content_data = self.request(
            token=self.new_user_token,
        )
        self.assertEquals(response.status_code, status.HTTP_200_OK)

    @patch("connect.common.signals.update_user_permission_project")
    def test_create_template_project(self, mock_permission):
        mock_permission.return_value = True
        data = {
            "date_format": "D",
            "name": "Test template project",
            "organization": str(self.organization.uuid),
            "timezone": "America/Argentina/Buenos_Aires",
            "template": True,
            "template_type": "support",
        }
        response, content_data = self.request_create(
            data, token=self.user_token
        )

        self.assertEquals(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNotNone(content_data.get("flow_uuid"))
        self.assertEquals(content_data.get("first_access"), True)
        self.assertEquals(content_data.get("wa_demo_token"), "wa-demo-12345")
        self.assertEquals(content_data.get("project_type"), "template:support")
