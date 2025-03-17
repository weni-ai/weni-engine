import requests


class OmieClient:  # pragma: no cover

    base_url = "https://app.omie.com.br/api/"
    headers = {
        "Content-type": "application/json",
    }

    def __init__(self, app_key: str, app_secret: str) -> None:
        self.app_key = app_key
        self.app_secret = app_secret

    def retrieve_account(self, account_code: str):
        path = "v1/crm/contas/"

        json_data = {
            "call": "ConsultarConta",
            "app_key": self.app_key,
            "app_secret": self.app_secret,
            "param": [
                {
                    "cCodInt": account_code,
                },
            ],
        }

        response = requests.post(
            f"{self.base_url}{path}", headers=self.headers, json=json_data
        )

        return response

    def list_accounts(self, page: int = 1, per_page: int = 20):
        path = "v1/crm/contas/"
        json_data = {
            "call": "ListarContas",
            "app_key": self.app_key,
            "app_secret": self.app_secret,
            "param": [
                {
                    "pagina": page,
                    "registros_por_pagina": per_page,
                },
            ],
        }
        response = requests.post(
            f"{self.base_url}{path}", headers=self.headers, json=json_data
        )

        return response

    def verify_account(self, name: str, email: str):
        path = "v1/crm/contas/"
        json_data = {
            "call": "VerificarConta",
            "app_key": self.app_key,
            "app_secret": self.app_secret,
            "param": [{"cNome": name, "cEmail": email}],
        }
        response = requests.post(
            f"{self.base_url}{path}", headers=self.headers, json=json_data
        )

        return response

    def list_origins(self, page: int = 1, per_page: int = 20):
        path = "v1/crm/origens/"
        json_data = {
            "call": "ListarOrigens",
            "app_key": self.app_key,
            "app_secret": self.app_secret,
            "param": [
                {
                    "pagina": page,
                    "registros_por_pagina": per_page,
                },
            ],
        }

        response = requests.post(
            f"{self.base_url}{path}", headers=self.headers, json=json_data
        )
        return response

    def list_solutions(self, page: int = 1, per_page: int = 20):
        path = "v1/crm/solucoes/"
        json_data = {
            "call": "ListarSolucoes",
            "app_key": self.app_key,
            "app_secret": self.app_secret,
            "param": [
                {
                    "pagina": page,
                    "registros_por_pagina": per_page,
                },
            ],
        }
        response = requests.post(
            f"{self.base_url}{path}", headers=self.headers, json=json_data
        )
        return response

    def list_users(self, page: int = 1, per_page: int = 20):
        path = "v1/crm/usuarios/"
        json_data = {
            "call": "ListarUsuarios",
            "app_key": self.app_key,
            "app_secret": self.app_secret,
            "param": [
                {
                    "pagina": page,
                    "registros_por_pagina": per_page,
                },
            ],
        }
        response = requests.post(
            f"{self.base_url}{path}", headers=self.headers, json=json_data
        )
        return response

    def get_users(self):
        path = "v1/crm/usuarios/"
        json_data = {
            "call": "ObterUsuarios",
            "app_key": self.app_key,
            "app_secret": self.app_secret,
            "param": [{"cExibirTodos": "S"}],
        }
        response = requests.post(
            f"{self.base_url}{path}", headers=self.headers, json=json_data
        )
        return response
