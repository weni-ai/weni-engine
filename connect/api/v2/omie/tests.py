import json
from connect.api.v2.omie.views import (
    OmieAccountAPIView,
    OmieOriginAPIView,
    OmieSolutionsAPIView,
    OmieUsersAPIView,
)
from rest_framework import status
from rest_framework.test import APIRequestFactory

from django.test import TestCase
from django.conf import settings

from unittest.mock import patch


class OmieAccResponse:
    status_code = 200

    @staticmethod
    def json():
        account_response = {
            "cadastros": [
                {
                    "caracteristicas": [],
                    "endereco": {},
                    "identificacao": {
                        "cCodInt": "001",
                        "cDoc": "",
                        "cNome": "Account 1",
                    },
                    "informacoesAdicionais": {},
                    "tags": [],
                    "telefone_email": {},
                },
                {
                    "caracteristicas": [],
                    "endereco": {},
                    "identificacao": {
                        "cCodInt": "002",
                        "cDoc": "",
                        "cNome": "Account 2",
                    },
                    "informacoesAdicionais": {},
                    "tags": [],
                    "telefone_email": {},
                },
                {
                    "caracteristicas": [],
                    "endereco": {},
                    "identificacao": {
                        "cCodInt": "003",
                        "cDoc": "",
                        "cNome": "Account 3",
                    },
                    "informacoesAdicionais": {},
                    "tags": [],
                    "telefone_email": {},
                },
            ]
        }
        return account_response


class OmieOriginResponse:
    status_code = 200

    @staticmethod
    def json():
        origin_response = {
            "cadastros": [
                {
                    "cDescricao": "Origin 1",
                    "cObservacao": "Origin (1)",
                    "nCodigo": 1234567890,
                },
                {
                    "cDescricao": "Origin 2",
                    "cObservacao": "Origin (2)",
                    "nCodigo": 9876543210,
                },
            ]
        }
        return origin_response


class OmieSolutionResponse:
    status_code = 200

    @staticmethod
    def json():
        return {
            "cadastros": [
                {
                    "cDescricao": "Solução 01",
                    "cInativo": "N",
                    "cObservacao": "",
                    "nCodigo": 1234567890,
                },
                {
                    "cDescricao": "Solução 02",
                    "cInativo": "N",
                    "cObservacao": "",
                    "nCodigo": 9876543210,
                },
            ]
        }


class OmieUserResponse:
    status_code = 200

    @staticmethod
    def json():
        return {
            "listaUsuarios": [
                {
                    "cEmail": "1.vendedor@email.ai",
                    "cNome": "1 vendedor",
                    "cTelefone": "(00) 00000-0000",
                    "nCodigo": 1231231234,
                },
                {
                    "cCelular": "+55 (11) 3775-7888",
                    "cEmail": "contato@omie.com.br",
                    "cNome": "Omiexperience",
                    "cTelefone": "+55 (11) 3775-7888",
                    "nCodigo": 2342342345,
                },
            ]
        }


class OmieAccountViewSetTestCase(TestCase):
    def setUp(self):
        self.app_key = settings.OMIE_APP_KEY
        self.app_secret = settings.OMIE_APP_SECRET
        self.factory = APIRequestFactory()
        self.omie_acc_response = OmieAccResponse()

    def request(self, path: str, method: dict):
        request = self.factory.get(path)

        response = OmieAccountAPIView.as_view()(request)
        response.render()

        content_data = json.loads(response.content)

        return response, content_data

    def test_invalid_app_credentials(self):
        path = "/v2/omie/accounts"
        method = {"get": "get"}

        response, content_data = self.request(
            path,
            method,
        )

        self.assertEquals(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("connect.api.clients.omie.OmieClient.list_accounts")
    def test_list_accounts(self, list_accounts):

        list_accounts.side_effect = [self.omie_acc_response]

        path = f"/v2/omie/origins?app_key={self.app_key}&app_secret={self.app_secret}"
        method = {"get": "get"}

        response, content_data = self.request(
            path,
            method,
        )

        self.assertEquals(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(content_data.get("accounts"))


class OmieOriginViewSetTestCase(TestCase):
    def setUp(self):
        self.app_key = settings.OMIE_APP_KEY
        self.app_secret = settings.OMIE_APP_SECRET
        self.factory = APIRequestFactory()
        self.omie_response = OmieOriginResponse()

    def request(self, path: str, method: dict):
        request = self.factory.get(path)

        response = OmieOriginAPIView.as_view()(request)
        response.render()

        content_data = json.loads(response.content)

        return response, content_data

    def test_invalid_app_credentials(self):
        path = "/v2/omie/accounts"
        method = {"get": "get"}

        response, content_data = self.request(
            path,
            method,
        )

        self.assertEquals(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("connect.api.clients.omie.OmieClient.list_origins")
    def test_list_origins(self, list_origins):

        list_origins.side_effect = [self.omie_response]

        path = f"/v2/omie/accounts?app_key={self.app_key}&app_secret={self.app_secret}"
        method = {"get": "get"}

        response, content_data = self.request(
            path,
            method,
        )

        self.assertEquals(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(content_data.get("origins"))


class OmieSolutionViewSetTestCase(TestCase):
    def setUp(self):
        self.app_key = settings.OMIE_APP_KEY
        self.app_secret = settings.OMIE_APP_SECRET
        self.factory = APIRequestFactory()
        self.omie_response = OmieSolutionResponse()

    def request(self, path: str, method: dict):
        request = self.factory.get(path)

        response = OmieSolutionsAPIView.as_view()(request)
        response.render()

        content_data = json.loads(response.content)

        return response, content_data

    def test_invalid_app_credentials(self):
        path = "/v2/omie/accounts"
        method = {"get": "get"}

        response, content_data = self.request(
            path,
            method,
        )

        self.assertEquals(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("connect.api.clients.omie.OmieClient.list_solutions")
    def test_list_solutions(self, list_solutions=None):

        list_solutions.side_effect = [self.omie_response]

        path = f"/v2/omie/accounts?app_key={self.app_key}&app_secret={self.app_secret}"
        method = {"get": "get"}

        response, content_data = self.request(
            path,
            method,
        )

        self.assertEquals(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(content_data.get("solutions"))


class OmieUserViewSetTestCase(TestCase):
    def setUp(self):
        self.app_key = settings.OMIE_APP_KEY
        self.app_secret = settings.OMIE_APP_SECRET
        self.factory = APIRequestFactory()
        self.omie_response = OmieUserResponse()

    def request(self, path: str, method: dict):
        request = self.factory.get(path)

        response = OmieUsersAPIView.as_view()(request)
        response.render()

        content_data = json.loads(response.content)

        return response, content_data

    def test_invalid_app_credentials(self):
        path = "/v2/omie/users"
        method = {"get": "get"}

        response, content_data = self.request(
            path,
            method,
        )

        self.assertEquals(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("connect.api.clients.omie.OmieClient.get_users")
    def test_list_users(self, get_users=None):

        get_users.side_effect = [self.omie_response]

        path = f"/v2/omie/users?app_key={self.app_key}&app_secret={self.app_secret}"
        method = {"get": "get"}

        response, content_data = self.request(
            path,
            method,
        )

        self.assertEquals(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(content_data.get("users"))
