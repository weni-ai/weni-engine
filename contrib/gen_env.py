"""
Responsible for speeding up the generation of a local '.env' configuration file.
OBS: Run in development/CI environment only.
"""

import os

from django.core.management.utils import get_random_secret_key


def dict_to_config_string(data: dict) -> str:
    config_string = ""
    for key, value in data.items():
        config_string += f'{key}="{value}"\n'

    return config_string.strip()


def generate_env() -> None:
    env_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"
    )

    if os.path.exists(env_path):
        print("A .env file already exists, delete it and run again")
        return

    variables = {
        "ENGINE_PORT": 8080,
        "SECRET_KEY": get_random_secret_key(),
        "OIDC_RP_REALM_NAME": "",
        "OIDC_RP_CLIENT_ID": "",
        "OIDC_OP_LOGOUT_ENDPOINT": "",
        "OIDC_RP_SCOPES": "",
        "OIDC_RP_CLIENT_SECRET": "",
        "OIDC_OP_TOKEN_ENDPOINT": "",
        "OIDC_OP_AUTHORIZATION_ENDPOINT": "",
        "OIDC_RP_SIGN_ALGO": "",
        "OIDC_RP_SERVER_URL": "",
        "OIDC_OP_USER_ENDPOINT": "",
        "OIDC_OP_JWKS_ENDPOINT": "",
        "BILLING_COST_PER_WHATSAPP": 199,
        "BILLING_TEST_MODE": True,
        "USE_EDA": True,
        "TESTING": True,
    }

    with open(env_path, "w") as configfile:
        configfile.write(dict_to_config_string(variables))


if __name__ == "__main__":
    generate_env()
