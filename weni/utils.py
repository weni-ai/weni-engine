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
