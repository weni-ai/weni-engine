import functools

import pendulum
import requests
from django.http import JsonResponse
from django_redis import get_redis_connection

from connect.common.models import Project


def upload_photo_rocket(
    server_rocket: str, jwt_token: str, avatar_url: str
) -> bool:  # pragma: no cover
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


def get_grpc_types():  # pragma: no cover
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
    tz = pendulum.timezone("America/Maceio")
    after = pendulum.parse(after).in_timezone(tz)
    before = pendulum.parse(before).in_timezone(tz)
    return project.get_contacts(before, after)


def check_module_permission(claims, user):
    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import Permission
    from django.contrib.contenttypes.models import ContentType

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


def rate_limit(requests=5, window=60, block_time=300):
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(*args, **kwargs):
            if len(args) > 1:
                request = args[1]
            else:
                request = args[0]

            if request.user.is_authenticated:
                client_id = f"user:{request.user.id}"
            else:
                client_id = f"ip:{_get_client_ip(request)}"

            path = request.path_info
            redis_key = f"ratelimit:{path}:{client_id}"
            block_key = f"ratelimit:blocked:{path}:{client_id}"

            redis_conn = get_redis_connection()

            if redis_conn.exists(block_key):
                block_ttl = redis_conn.ttl(block_key)
                return JsonResponse(
                    {
                        "error": "Too many requests. Please try again later.",
                        "retry_after": block_ttl,
                    },
                    status=429,
                )

            pipe = redis_conn.pipeline()
            pipe.incr(redis_key)
            pipe.expire(redis_key, window)
            results = pipe.execute()
            request_count = results[0]

            if request_count > requests:
                redis_conn.setex(block_key, block_time, 1)
                return JsonResponse(
                    {
                        "error": "Too many requests. Please try again later.",
                        "retry_after": block_time,
                    },
                    status=429,
                )

            return view_func(*args, **kwargs)

        return wrapper

    return decorator


def _get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip
