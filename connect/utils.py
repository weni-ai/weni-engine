import requests


def upload_photo_rocket(server_rocket: str, jwt_token: str, avatar_url: str) -> bool:
    login = requests.post(
        url="{}/api/v1/login/".format(server_rocket),
        json={"serviceName": "keycloak", "accessToken": jwt_token, "expiresIn": 200},
    ).json()

    set_photo = requests.post(
        url="{}/api/v1/users.setAvatar".format(server_rocket),
        headers={
            "X-Auth-Token": login.get("data", {}).get("authToken"),
            "X-User-Id": login.get("data", {}).get("userId"),
        },
        json={"avatarUrl": avatar_url},
    )
    return True if set_photo.status_code == 200 else False


def get_grpc_types():
    """
    Returns the possible types available for classifiers
    :return:
    """
    from connect.grpc import TYPES

    return TYPES


def calculate_active_contacts(value: int):
    base_value = {
        1000: 0.267,
        5000: 0.178,
        10000: 0.167,
        30000: 0.156,
        50000: 0.144,
        100000: 0.140,
        250000: 0.133,
    }
    if value < 1000:
        return 1000 * base_value.get(1000)
    elif value < 5000:
        return value * base_value.get(1000)
    elif 5000 <= value < 10000:
        return value * base_value.get(5000)
    elif 10000 <= value < 30000:
        return value * base_value.get(10000)
    elif 30000 <= value < 50000:
        return value * base_value.get(30000)
    elif 50000 <= value < 100000:
        return value * base_value.get(50000)
    elif 100000 <= value < 250000:
        return value * base_value.get(100000)
    elif value >= 250000:
        return value * base_value.get(250000)
