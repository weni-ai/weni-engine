from django_redis import get_redis_connection

from weni_commons.auth import (
    DynamoDBSessionTokenRepository,
    ValidateSessionTokenUseCase,
    evict_cache,
)


class SessionTokenNotFound(Exception):
    pass


class SessionTokenProjectMismatch(Exception):
    pass


class InvalidateSessionTokenUseCase:
    def __init__(
        self, redis_connection=None, dynamodb_repository=None, validator=None
    ) -> None:
        self._redis = redis_connection
        self._dynamodb_repository = dynamodb_repository
        self._validator = validator

    def _get_dynamodb_repository(self) -> DynamoDBSessionTokenRepository:
        if self._dynamodb_repository is None:
            self._dynamodb_repository = DynamoDBSessionTokenRepository()
        return self._dynamodb_repository

    def _get_validator(self) -> ValidateSessionTokenUseCase:
        if self._validator is None:
            self._validator = ValidateSessionTokenUseCase(
                redis_connection=self._redis,
                dynamodb_repository=self._get_dynamodb_repository(),
            )
        return self._validator

    def execute(self, token_hash: str, requester_projeto: str) -> None:
        session = self._get_validator().execute(token_hash)
        if session is None:
            raise SessionTokenNotFound()

        if session.projeto != str(requester_projeto):
            raise SessionTokenProjectMismatch()

        redis_connection = self._redis or get_redis_connection()
        evict_cache(redis_connection, token_hash)
        self._get_dynamodb_repository().delete(token_hash)
