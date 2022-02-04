import json
import uuid as uuid4
from unittest.mock import patch

from django.test import RequestFactory
from django.test import TestCase
from django.test.client import MULTIPART_CONTENT
from django.conf import settings
from rest_framework import status

from connect.api.v1.project.views import ProjectViewSet
from connect.api.v1.tests.utils import create_user_and_token
from connect.common.models import (
    Project,
    Organization,
    BillingPlan,
    OrganizationRole,
    ProjectRoleLevel,
)


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

    @patch("connect.common.tasks.create_project.delay")
    def test_okay(self, task_create_project):
        task_create_project.return_value.result = {"uuid": uuid4.uuid4()}
        response, content_data = self.request(
            {
                "name": "Project 1",
                "organization": self.organization.uuid,
                "date_format": "D",
                "timezone": "America/Sao_Paulo",
            },
            self.owner_token,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        project = Project.objects.get(pk=content_data.get("uuid"))

        self.assertEqual(project.name, "Project 1")

        self.assertEqual(
            project.__str__(),
            f"{project.uuid} - Project: {project.name} - Org: {project.organization.name}",
        )


class ListProjectAPITestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.owner, self.owner_token = create_user_and_token("owner")
        self.user, self.user_token = create_user_and_token("user")
        self.finacial, self.finacial_token = create_user_and_token("finacial")
        self.organization = Organization.objects.create(
            name="test organization",
            description="",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="free",
        )
        self.owner_organization_authorization = self.organization.authorizations.create(
            user=self.owner, role=OrganizationRole.ADMIN.value
        )
        self.user_organization_authorization = self.organization.authorizations.create(
            user=self.user, role=OrganizationRole.CONTRIBUTOR.value
        )
        self.financial_organization_authorization = (
            self.organization.authorizations.create(
                user=self.finacial, role=OrganizationRole.FINANCIAL.value
            )
        )
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
        self.owner_project_authorization = self.project.project_authorizations.create(
            user=self.owner,
            role=ProjectRoleLevel.ADMIN.value,
            organization_authorization=self.owner_organization_authorization,
        )
        self.owner_project_authorization2 = self.project2.project_authorizations.create(
            user=self.owner,
            role=ProjectRoleLevel.ADMIN.value,
            organization_authorization=self.owner_organization_authorization,
        )
        self.user_project_authorization = self.project.project_authorizations.create(
            user=self.user,
            role=ProjectRoleLevel.ADMIN.value,
            organization_authorization=self.user_organization_authorization,
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
        self.assertEqual(content_data.get("count"), 1)

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
            self.finacial_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(content_data.get("count"), 0)


class UpdateProjectTestCase(TestCase):
    def setUp(self):
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

    def test_okay_update_name(self):
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

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class ProjectEmailTestCase(TestCase):
    def setUp(self):
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
        self.test_email = "test@example.com"
        self.test_user_name = "test_username"
        self.test_first_name = "test"
        self.organization_new_name = "Test Org"

    def test_send_email_change_project(self):
        info = {
            "old_project_name": "name_test",
            "date_before": "DD-MM-AAAA",
            "old_timezone": "(GMT -03:00) America / Argentina / Buenos Aires",
            "country_loc_suport_before": "Argentina",
            "country_loc_suport_now": "Brasil",
            "default_lang_before": "Espanhol",
            "default_lang_now": "Português do Brasil",
            "secondary_lang_before": "Espanhol",
            "secondary_lang_now": "Espanhol",
            "user": "João",
        }

        sended_mail = self.project.send_email_change_project(
            self.test_first_name, self.test_email, info
        )
        self.assertEqual(len(sended_mail.outbox), 1)
        outbox = sended_mail.outbox[0]
        self.assertEqual(outbox.subject, f"The project {self.project.name} has changed")
        self.assertEqual(outbox.from_email, settings.DEFAULT_FROM_EMAIL)
        self.assertEqual(outbox.to[0], self.test_email)

    def test_send_email_deleted_project(self):
        sended_mail = self.project.send_email_deleted_project(
            self.test_first_name, self.test_email
        )
        self.assertEqual(len(sended_mail.outbox), 1)
        outbox = sended_mail.outbox[0]
        self.assertEqual(outbox.subject, "A project was deleted...")
        self.assertEqual(outbox.from_email, settings.DEFAULT_FROM_EMAIL)
        self.assertEqual(outbox.to[0], self.test_email)
