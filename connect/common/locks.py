import logging
from contextlib import contextmanager
from typing import Iterator, Optional

from django_redis import get_redis_connection
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


class LockNotAcquiredError(Exception):
    """Raised when a Redis lock could not be acquired within the wait window."""


class RedisLockService:
    """Cross-process mutual exclusion backed by Redis.

    Serializes critical sections that span multiple statements (e.g. a
    uniqueness check followed by a write) and could otherwise interleave
    between concurrent processes.

    The lock carries a TTL so a crashed holder cannot block the key forever,
    and a blocking timeout so callers fail fast instead of hanging. When Redis
    is unreachable the section is allowed to proceed *unlocked*: the guarantee
    is best-effort and must not take the feature down during a Redis outage.
    """

    def __init__(
        self,
        ttl: int = 10,
        blocking_timeout: int = 10,
        connection=None,
    ):
        self._ttl = ttl
        self._blocking_timeout = blocking_timeout
        self._connection = connection

    @property
    def connection(self):
        if self._connection is None:
            self._connection = get_redis_connection()
        return self._connection

    @contextmanager
    def lock(self, key: str) -> Iterator[None]:
        redis_lock = self._acquire(key)
        if redis_lock is None:
            yield
            return

        try:
            yield
        finally:
            self._release(key, redis_lock)

    def _acquire(self, key: str) -> Optional[object]:
        """Return the acquired lock, or ``None`` when Redis is unavailable.

        A ``None`` return signals the caller to proceed without locking,
        keeping the feature working during a Redis outage (and in test/CI
        environments that have no Redis).
        """
        try:
            redis_lock = self.connection.lock(
                key,
                timeout=self._ttl,
                blocking_timeout=self._blocking_timeout,
            )
            acquired = redis_lock.acquire()
        except RedisError as exc:
            logger.warning(
                f"Redis unavailable for lock key={key}; proceeding unlocked: {exc}"
            )
            return None

        if not acquired:
            raise LockNotAcquiredError(
                f"Could not acquire lock for key={key} within "
                f"{self._blocking_timeout}s."
            )
        return redis_lock

    @staticmethod
    def _release(key: str, redis_lock) -> None:
        try:
            redis_lock.release()
        except Exception as exc:
            logger.warning(f"Lock key={key} already released or expired: {exc}")
