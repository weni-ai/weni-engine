from dataclasses import dataclass
import random
import string

from django.contrib.auth import get_user_model

from connect.api.v1.keycloak import KeycloakControl

from connect.usecases.users.user_dto import KeycloakUserDTO

User = get_user_model()


@dataclass
class CreateKeycloakUserUseCase:
    user_dto: KeycloakUserDTO

    def generate_password(self) -> str:
        uppercase = string.ascii_uppercase
        lowercase = string.ascii_lowercase
        digits = string.digits
        special = "!@#$%^&*()_+-=[]{}|;:,.<>?"

        password = [
            random.choice(uppercase),  # 1 uppercase
            random.choice(lowercase),  # 1 lowercase
            random.choice(digits),  # 1 digit
            random.choice(special),  # 1 special
        ]

        all_chars = uppercase + lowercase + digits + special
        password.extend(random.choices(all_chars, k=4))

        random.shuffle(password)

        return "".join(password)

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
                company_name=self.user_dto.company_name,
            )

            return {
                "user": user,
                "keycloak_user": keycloak_user,
                "password": password,
            }
        except Exception as e:
            raise e
