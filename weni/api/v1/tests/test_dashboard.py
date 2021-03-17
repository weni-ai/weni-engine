import json
import uuid

from django.test import RequestFactory, TestCase
from rest_framework import status

from weni.api.v1.dashboard.views import StatusServiceViewSet
from weni.api.v1.tests.utils import create_user_and_token
from weni.common.models import Service, Organization, OrganizationAuthorization


class ListStatusServiceTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

        self.service = Service.objects.create(
            url="http://test.com", status=False, default=True
        )

        self.user, self.token = create_user_and_token()

        self.organization = Organization.objects.create(
            name="test organization", description="", inteligence_organization=1
        )

        self.organization_authorization = self.organization.authorizations.create(
            user=self.user, role=OrganizationAuthorization.ROLE_ADMIN
        )

        self.project = self.organization.project.create(
            name="project test",
            timezone="America/Sao_Paulo",
            flow_organization=uuid.uuid4(),
        )

    def request(self, token):
        authorization_header = {"HTTP_AUTHORIZATION": "Token {}".format(token)}
        request = self.factory.get(
            "/v1/dashboard/status-service/", **authorization_header
        )
        response = StatusServiceViewSet.as_view({"get": "list"})(request)
        response.render()
        content_data = json.loads(response.content)
        return (response, content_data)

    def test_status_okay(self):
        response, content_data = self.request(self.token)
        self.assertEqual(content_data["count"], 1)
        self.assertEqual(len(content_data["results"]), 1)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
