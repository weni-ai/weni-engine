import json

from django.test import RequestFactory, TestCase
from rest_framework import status

from connect.api.v1.dashboard.views import StatusServiceViewSet
from connect.api.v1.tests.utils import create_user_and_token
from connect.common.models import Service


class ListStatusServiceTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

        self.service = Service.objects.create(
            url="http://test.com", status=False, default=True
        )

        self.user, self.token = create_user_and_token()

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
