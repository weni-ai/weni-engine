import requests
from django.conf import settings


class OmieClient:
    app_key = settings.OMIE_APP_KEY
    app_secret = settings.OMIE_APP_SECRET
    base_url = "https://app.omie.com.br/api/"
    headers = {
        'Content-type': 'application/json',
    }

    def retrieve_account(self, account_code: str):
        path = "v1/crm/contas/"

        json_data = {
            'call': 'ConsultarConta',
            'app_key': self.app_key,
            'app_secret': self.app_secret,
            'param': [
                {
                    'cCodInt': account_code,
                },
            ],
        }

        response = requests.post(
            f"{self.base_url}{path}",
            headers=self.headers,
            json=json_data
        )

        return response

    def list_account(self, page: int = 1, per_page: int = 20):
        path = "v1/crm/contas/"
        json_data = {
            'call': 'ListarContas',
            'app_key': self.app_key,
            'app_secret': self.app_secret,
            'param': [
                {
                    'pagina': page,
                    'registros_por_pagina': per_page,
                },
            ],
        }
        response = requests.post(
            f"{self.base_url}{path}",
            headers=self.headers,
            json=json_data
        )

        return response

    def list_origins(self, page: int = 1, per_page: int = 20):
        path = "v1/crm/origens/"
        json_data = {
            'call': 'ListarOrigens',
            'app_key': self.app_key,
            'app_secret': self.app_secret,
            'param': [
                {
                    'pagina': page,
                    'registros_por_pagina': per_page,
                },
            ],
        }

        response = requests.post(
            f"{self.base_url}{path}",
            headers=self.headers,
            json=json_data
        )
        return response

    def list_solutions(self, page: int = 1, per_page: int = 20):
        path = "v1/crm/solucoes/"
        json_data = {
            'call': 'ListarSolucoes',
            'app_key': self.app_key,
            'app_secret': self.app_secret,
            'param': [
                {
                    'pagina': page,
                    'registros_por_pagina': per_page,
                },
            ],
        }
        response = requests.post(
            f"{self.base_url}{path}",
            headers=self.headers,
            json=json_data
        )
        return response
