import json
from django.test import RequestFactory
from django.test import TestCase
from ..organization.serializers import User

from connect.api.v1.organization.views import OrganizationViewSet
from connect.api.v1.tests.utils import create_user_and_token
from connect.common.models import (
    OrganizationAuthorization,
    Project,
    ProjectAuthorization,
    RequestPermissionOrganization,
)


class CreateOrganizationAPITestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.owner, self.owner_token = create_user_and_token("owner")

    def request(self, data, token=None):
        authorization_header = (
            {"HTTP_AUTHORIZATION": "Token {}".format(token.key)} if token else {}
        )

        request = self.factory.post(
            "/v1/organization/org/",
            json.dumps(data),
            content_type="application/json",
            format="json",
            **authorization_header,
        )

        response = OrganizationViewSet.as_view({"post": "create"})(request, data)
        response.render()
        content_data = json.loads(response.content)
        return (response, content_data)

    def test_create(self):
        User.objects.create(
            email="e@mail.com",
        )
        data = {
            "organization": {
                "name": "name",
                "description": "desc",
                "plan": "plan",
                "authorizations": [
                    {
                        "user_email": "e@mail.com",
                        "role": 3
                    }
                ]
            },
            "project": {
                "date_format": "D",
                "name": "Test Project",
                "organization": "2575d1f9-f7f8-4a5d-ac99-91972e309511",
                "timezone": "America/Argentina/Buenos_Aires",
            }
        }

        response, content_data = self.request(data, self.owner_token)
        self.assertEquals(response.status_code, 201)

    def test_create_template_project(self):
        data = {
            "organization": {
                "name": "name",
                "description": "desc",
                "plan": "plan",
                "authorizations": [
                    {
                        "user_email": "e@mail.com",
                        "role": 3
                    }
                ]
            },
            "project": {
                "date_format": "D",
                "name": "Test Project",
                "organization": "2575d1f9-f7f8-4a5d-ac99-91972e309511",
                "timezone": "America/Argentina/Buenos_Aires",
                "template": True
            }
        }
        response, content_data = self.request(data, self.owner_token)

        self.assertEquals(response.status_code, 201)
        self.assertEquals(content_data.get("project").get("first_access"), True)
        self.assertEquals(content_data.get("project").get("wa_demo_token"), "wa-demo-12345")
        self.assertEquals(content_data.get("project").get("project_type"), "template")
        self.assertEquals(OrganizationAuthorization.objects.count(), 1)
        self.assertEquals(RequestPermissionOrganization.objects.count(), 1)
        self.assertEquals(Project.objects.count(), 1)
        self.assertEquals(ProjectAuthorization.objects.count(), 1)
