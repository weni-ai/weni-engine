import requests
import pendulum
from connect.common.models import Project
from connect.billing.models import ContactCount


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


def count_contacts(project: Project, before: str, after: str):
    contacts_day_count = ContactCount.objects.filter(
        channel__project=project,
        created_at__lte=before,
        created_at__gte=after
    )
    return sum([day_count.count for day_count in contacts_day_count])
