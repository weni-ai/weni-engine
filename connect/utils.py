import requests
import pendulum
from connect.common.models import Project, BillingPlan
from connect.billing.models import Contact, ContactCount


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
    # contacts_day_count = ContactCount.objects.filter(project=project).filter(created_at__range=(after, before))
    # contacts_day_count = Contact.objects.filter(project=project).filter(last_seen_on__range=(after, before)).distinct("contact_flow_uuid").count()
    tz = pendulum.timezone("America/Maceio")
    after = pendulum.parse(after).in_timezone(tz)
    before = pendulum.parse(before).in_timezone(tz)

    if project.organization.organization_billing.plan in [BillingPlan.PLAN_CUSTOM, BillingPlan.PLAN_ENTERPRISE]:
        total_for_custom = Contact.objects.filter(project=project).filter(last_seen_on__range=(after, before)).distinct("contact_flow_uuid").count()
        return total_for_custom

    contacts_day_count = ContactCount.objects.filter(project=project, day__range=(after, before))
    total = sum([day_count.count for day_count in contacts_day_count])
    return total


def check_module_permission(claims, user):
    from django.contrib.auth.models import Permission
    from django.contrib.contenttypes.models import ContentType
    from django.contrib.auth import get_user_model
    User = get_user_model()

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
