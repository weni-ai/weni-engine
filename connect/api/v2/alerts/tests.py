import json

from rest_framework.test import APIRequestFactory
from django.test import TestCase
from django.conf import settings

from .views import AlertViewSet
from connect.usecases.alerts.tests.alerts_factory import AlertFactory


class AlertViewSetTestCase(TestCase):
    def setUp(self) -> None:
        self.token = settings.VERIFICATION_MARKETING_TOKEN

        self.factory = APIRequestFactory()
        self.view = AlertViewSet.as_view(
            {"get": "list", "post": "create", "put": "update", "delete": "destroy"}
        )
        self.alert = AlertFactory()
        self.url = "/api/v2/alerts/"

    def test_get_queryset(self):
        request = self.factory.get(
            self.url,
            HTTP_AUTHORIZATION=self.token,
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 200)

    def test_retrieve(self):

        url_retrieve = f"{self.url}{self.alert.uuid}/"
        request = self.factory.get(
            url_retrieve,
            HTTP_AUTHORIZATION=self.token,
        )
        response = AlertViewSet.as_view({"get": "retrieve"})(
            request, alert_uuid=self.alert.uuid
        )
        self.assertEqual(response.status_code, 200)

    def test_create(self):

        data = {"can_be_closed": True, "text": "string", "type": 1}
        request = self.factory.post(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION=self.token,
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 201)

    def test_update(self):

        url_put = f"{self.url}/{self.alert.uuid}/"
        data = {"can_be_closed": True, "text": "string", "type": 1}
        request = self.factory.put(
            url_put,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION=self.token,
        )
        response = self.view(request, alert_uuid=self.alert.uuid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.get("can_be_closed"), True)

    def test_delete(self):

        url_delete = f"{self.url}/{self.alert.uuid}/"
        request = self.factory.delete(
            url_delete,
            HTTP_AUTHORIZATION=self.token,
        )
        response = self.view(request, alert_uuid=self.alert.uuid)
        self.assertEqual(response.status_code, 204)
