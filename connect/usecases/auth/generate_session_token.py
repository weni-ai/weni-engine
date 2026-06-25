import json
import secrets
from datetime import timedelta
from django.utils import timezone
from django_redis import get_redis_connection

CACHE_KEY_TEMPLATE = "auth:session-token:{hash}"


def build_cache_key(token_hash: str) -> str:
    return CACHE_KEY_TEMPLATE.format(hash=token_hash)


class GenerateSessionTokenUseCase:
    def __init__(self, redis_connection=None) -> None:
        self._redis = redis_connection

    def execute(self, project_uuid: str, user_email: str, duration: int) -> str:
        token_hash = secrets.token_urlsafe(32)
        expire_at = timezone.now() + timedelta(seconds=duration)

        payload = {
            "projeto": str(project_uuid),
            "user": user_email,
            "expire_at": expire_at.isoformat(),
        }

        redis_connection = self._redis or get_redis_connection()
        redis_connection.setex(
            build_cache_key(token_hash),
            duration,
            json.dumps(payload),
        )

        return token_hash
