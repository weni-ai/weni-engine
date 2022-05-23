import requests
import pendulum


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


def es_convert_datetime(before: str, after: str):
    """convert to an format that is accepted by elasticsearch query"""
    before = pendulum.parse(before)
    after = pendulum.parse(after)
    return before, after


def check_module_permission(claims, user):
    from django.contrib.auth.models import Permission
    from django.contrib.contenttypes.models import ContentType
    from connect.authentication.models import User

    if claims.get("can_communicate_internally", False):
        content_type = ContentType.objects.get_for_model(User)
        permission, created = Permission.objects.get_or_create(
            codename="can_communicate_internally",
            name="can communicate internally",
            content_type=content_type,
        )
        if not user.has_perm("authentication.can_communicate_internally"):
            user.user_permissions.add(permission)
        return True
    return False
