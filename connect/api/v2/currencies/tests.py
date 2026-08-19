import json

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from connect.api.v1.tests.utils import create_user_and_token
from connect.api.v2.currencies.views import CurrenciesView
from connect.common.currencies import list_currency_codes


class CurrenciesViewTestCase(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user, _ = create_user_and_token("currencies_view_user")

    def test_returns_currency_codes_for_authenticated_user(self):
        request = self.factory.get("/v2/currencies")
        force_authenticate(request, user=self.user)

        response = CurrenciesView.as_view()(request)
        response.render()
        content = json.loads(response.content)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(content["currencies"], list(list_currency_codes()))
        self.assertIn("BRL", content["currencies"])

    def test_unauthenticated_request_is_rejected(self):
        request = self.factory.get("/v2/currencies")
        response = CurrenciesView.as_view()(request)

        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
