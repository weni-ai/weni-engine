import json

from django.test import TestCase, RequestFactory
from django.test.client import MULTIPART_CONTENT
from rest_framework import status

from connect.api.v1.account.views import MyUserProfileViewSet
from connect.api.v1.tests.utils import create_user_and_token


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


class UserUpdateTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user, self.user_token = create_user_and_token()

    def request(self, user, data, token):
        authorization_header = {"HTTP_AUTHORIZATION": "Token {}".format(token.key)}
        request = self.factory.patch(
            "/v1/account/my-profile/",
            self.factory._encode_data(data, MULTIPART_CONTENT),
            MULTIPART_CONTENT,
            **authorization_header
        )
        response = MyUserProfileViewSet.as_view({"patch": "update"})(
            request, pk=user.pk, partial=True
        )
        response.render()
        content_data = json.loads(response.content)
        return (response, content_data)

    def test_update_phone(self):
        response, content_data = self.request(
            self.user, {"phone": 996498826, "short_phone_prefix": 55}, self.user_token
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(content_data.get("phone"), 996498826)
        self.assertEqual(content_data.get("short_phone_prefix"), 55)

    def test_update_utm(self):
        response, content_data = self.request(
            self.user, {"utm": json.dumps("{'utm_source': 'weni'}")}, self.user_token
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(content_data.get("utm"), "{'utm_source': 'weni'}")


class DestroyMyProfileTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user, self.user_token = create_user_and_token()

    def request(self, token):
        authorization_header = {"HTTP_AUTHORIZATION": "Token {}".format(token.key)}
        request = self.factory.delete("/v1/account/my-profile/", **authorization_header)
        response = MyUserProfileViewSet.as_view({"delete": "destroy"})(request)
        response.render()
        return response

    def test_okay(self):
        response = self.request(self.user_token)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
