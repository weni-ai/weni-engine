from dataclasses import dataclass
import random
import string

from django.core.mail import send_mail
from django.template.loader import render_to_string

from django.contrib.auth import get_user_model

from connect.api.v1.keycloak import KeycloakControl

from connect.usecases.users.user_dto import KeycloakUserDTO

User = get_user_model()


@dataclass
class CreateKeycloakUserUseCase:
    user_dto: KeycloakUserDTO

    def generate_password(self) -> str:
        return "".join(random.choices(string.ascii_letters + string.digits, k=10))

    def execute(self) -> dict:
        try:
            if not self.user_dto.email:
                raise ValueError("Email is required")

            keycloak_client = KeycloakControl()

            if not self.user_dto.credentials:
                password = self.generate_password()
                self.user_dto.credentials = [
                    {
                        "type": "password",
                        "value": password,
                        "temporary": True,
                    }
                ]

            keycloak_user = keycloak_client.instance.create_user(
                {
                    "username": self.user_dto.username,
                    "email": self.user_dto.username,
                    "enabled": True,
                    "credentials": self.user_dto.credentials,
                }
            )
            user = User.objects.create_user(
                username=self.user_dto.username,
                email=self.user_dto.username,
            )

            return {
                "user": user,
                "keycloak_user": keycloak_user,
                "password": password,
            }
        except Exception as e:
            raise e
