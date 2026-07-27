import secrets
from datetime import timedelta

from django.utils import timezone
from django_redis import get_redis_connection

from weni_commons.auth import (
    DynamoDBSessionTokenRepository,
    compute_redis_ttl,
    warm_cache,
)

CACHE_KEY_TEMPLATE = "auth:session-token:{hash}"


class GenerateSessionTokenUseCase:
    def __init__(self, redis_connection=None, dynamodb_repository=None) -> None:
        self._redis = redis_connection
        self._dynamodb_repository = dynamodb_repository

    def _get_dynamodb_repository(self) -> DynamoDBSessionTokenRepository:
        if self._dynamodb_repository is None:
            self._dynamodb_repository = DynamoDBSessionTokenRepository()
        return self._dynamodb_repository

    def execute(self, project_uuid: str, user_email: str, duration: int) -> str:
        token_hash = secrets.token_urlsafe(32)
        expire_at = (timezone.now() + timedelta(seconds=duration)).isoformat()

        payload = {
            "projeto": str(project_uuid),
            "user": user_email,
            "expire_at": expire_at,
        }

        self._get_dynamodb_repository().put(
            token_hash=token_hash,
            projeto=str(project_uuid),
            user=user_email,
            expire_at=expire_at,
        )

        redis_connection = self._redis or get_redis_connection()
        warm_cache(
            redis_connection,
            token_hash,
            payload,
            compute_redis_ttl(expire_at),
        )

        return token_hash
