import json
import requests
from django.conf import settings
from django.utils.crypto import get_random_string


class Rocket:
    def __init__(self):
        self.client_id = getattr(settings, "ROCKET_CLIENT_ID")
        self.username = getattr(settings, "ROCKET_USERNAME")
        self.password = getattr(settings, "ROCKET_PASSWORD")
        self.keycloak_oidc_url = getattr(settings, "KEYCLOAK_OIDC_URL")
        self.rocket_base_url = getattr(settings, "ROCKET_BASE_URL")
        self.is_authenticated = self.authenticate()
        self.valid_roles = ['admin', 'user', 'livechat-manager', 'livechat-agent']

    def get_keycloak_authorization_token(self):
        data = {
            "client_id": self.client_id,
            "username": self.username,
            "password": self.password,
            "grant_type": "password",
        }

        r = requests.post(self.keycloak_oidc_url, data)
        data = json.loads(r.text)

        if r.status_code == 200:
            return {
                "status": "SUCCESS",
                "access_token": data["access_token"],
                "expires_in": data["expires_in"],
            }

        return {"status": "FAILED", "message": data}

    def login_rocket(self):
        data = {
            "serviceName": "keycloak",
            "accessToken": self.keycloak_credentials["access_token"],
            "expiresIn": int(self.keycloak_credentials["expires_in"]),
        }

        headers = {"Content-Type": "application/json"}
        r = requests.post(
            self.rocket_base_url + "/login/", headers=headers, data=json.dumps(data)
        )
        response = json.loads(r.text)

        if r.status_code == 200:
            return {
                "status": "SUCCESS",
                "X-Auth-Token": response["data"]["authToken"],
                "X-User-Id": response["data"]["userId"],
            }

        return {
            "status": "FAILED",
        }

    def authenticate(self):
        self.keycloak_credentials = self.get_keycloak_authorization_token()
        if self.keycloak_credentials["status"] == "FAILED":
            return False, "Could not connect to keycloak"
        self.rocket_credentials = self.login_rocket()
        if self.rocket_credentials["status"] == "FAILED":
            return False, "Could not connect to rocket"
        return True, "Connected"

    def add_user_role(self, role_name: str, username: str):
        is_authenticated, message = self.is_authenticated
        if is_authenticated:
            if role_name in self.valid_roles:
                path = "/roles.addUserToRole"
                headers = {
                    "Content-Type": "application/json",
                    "X-Auth-Token": self.rocket_credentials["X-Auth-Token"],
                    "X-User-Id": self.rocket_credentials["X-User-Id"],
                }
                data = {"roleName": role_name, "username": username}

                r = requests.post(
                    self.rocket_base_url + path, headers=headers, data=json.dumps(data)
                )
                data = json.loads(r.text)
                return data
            return 'Invalid role name'
        return message

    def remove_user_role(self, role_name, username):
        is_authenticated, message = self.is_authenticated
        if is_authenticated:
            path = "/roles.removeUserFromRole"
            headers = {
                "Content-Type": "application/json",
                "X-Auth-Token": self.rocket_credentials["X-Auth-Token"],
                "X-User-Id": self.rocket_credentials["X-User-Id"],
            }
            data = {"roleName": role_name, "username": username}
            r = requests.post(
                self.rocket_base_url + path, headers=headers, data=json.dumps(data)
            )
            data = json.loads(r.text)
            return data

        return message

    def create_user(self, name, email):
        is_authenticated, message = self.is_authenticated
        if is_authenticated:
            password = get_random_string()
            print(password)
            username = email.split("@")[0]
            path = "/users.create"
            headers = {
                "Content-Type": "application/json",
                "X-Auth-Token": self.rocket_credentials["X-Auth-Token"],
                "X-User-Id": self.rocket_credentials["X-User-Id"],
            }
            data = {"name": name, "email": email, "password": password, "username": username}
            r = requests.post(
                self.rocket_base_url + path, headers=headers, data=json.dumps(data)
            )
            data = json.loads(r.text)
            return data
        return message

    def get_user(self, username):
        is_authenticated, message = self.is_authenticated
        if is_authenticated:
            path = f"/users.info?username={username}"
            headers = {
                "Content-Type": "application/json",
                "X-Auth-Token": self.rocket_credentials["X-Auth-Token"],
                "X-User-Id": self.rocket_credentials["X-User-Id"],
            }
            r = requests.get(
                self.rocket_base_url + path, headers=headers
            )
            data = json.loads(r.text)
            return data
        return message
