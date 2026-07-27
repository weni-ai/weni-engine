import secrets
from datetime import timedelta

from django.utils import timezone
from django_redis import get_redis_connection

from connect.common.models import ProjectAuthorization
from weni_commons.auth import (
    DynamoDBSessionTokenRepository,
    compute_redis_ttl,
    warm_cache,
)

CACHE_KEY_TEMPLATE = "auth:session-token:{hash}"
SESSION_TOKEN_NBYTES = 32


class ProjectAuthorizationNotFound(Exception):
    pass


class GenerateSessionTokenUseCase:
    def __init__(self, redis_connection=None, dynamodb_repository=None) -> None:
        self._redis = redis_connection
        self._dynamodb_repository = dynamodb_repository

    def _get_dynamodb_repository(self) -> DynamoDBSessionTokenRepository:
        if self._dynamodb_repository is None:
            self._dynamodb_repository = DynamoDBSessionTokenRepository()
        return self._dynamodb_repository

    def execute(self, project_uuid: str, user, duration: int) -> str:
        try:
            if not user.project_authorizations_user.filter(project__uuid=project_uuid).exists():
                raise ProjectAuthorizationNotFound()

        except ProjectAuthorization.DoesNotExist:
            raise ProjectAuthorizationNotFound()

        token_hash = secrets.token_urlsafe(SESSION_TOKEN_NBYTES)
        expire_at = (timezone.now() + timedelta(seconds=duration)).isoformat()

        payload = {
            "project": str(project_uuid),
            "user": user.email,
            "expire_at": expire_at,
        }

        self._get_dynamodb_repository().put(
            token_hash=token_hash,
            project=str(project_uuid),
            user=user.email,
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
