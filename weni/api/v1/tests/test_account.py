import json

from django.test import TestCase, RequestFactory
from rest_framework import status

from weni.api.v1.account.views import MyUserProfileViewSet
from weni.api.v1.tests.utils import create_user_and_token


class ListMyProfileTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user, self.user_token = create_user_and_token()

    def request(self, token):
        authorization_header = {"HTTP_AUTHORIZATION": "Token {}".format(token.key)}
        request = self.factory.get("/v2/account/my-profile/", **authorization_header)
        response = MyUserProfileViewSet.as_view({"get": "retrieve"})(request)
        response.render()
        content_data = json.loads(response.content)
        return (response, content_data)

    def test_okay(self):
        response, content_data = self.request(self.user_token)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(content_data.get("username"), self.user.username)
