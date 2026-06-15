from unittest.mock import MagicMock, patch

from django.test import TestCase
from redis.exceptions import ConnectionError as RedisConnectionError

from connect.common.locks import LockNotAcquiredError, RedisLockService


class RedisLockServiceTestCase(TestCase):
    def setUp(self):
        self.redis_lock = MagicMock()
        self.connection = MagicMock()
        self.connection.lock.return_value = self.redis_lock
        self.service = RedisLockService(connection=self.connection)

    def test_acquires_and_releases_lock_around_section(self):
        self.redis_lock.acquire.return_value = True

        with self.service.lock("my-key"):
            self.redis_lock.acquire.assert_called_once()
            self.redis_lock.release.assert_not_called()

        self.redis_lock.release.assert_called_once()

    def test_releases_lock_even_when_section_raises(self):
        self.redis_lock.acquire.return_value = True

        with self.assertRaises(ValueError):
            with self.service.lock("my-key"):
                raise ValueError("boom")

        self.redis_lock.release.assert_called_once()

    def test_raises_when_lock_not_acquired(self):
        self.redis_lock.acquire.return_value = False

        with self.assertRaises(LockNotAcquiredError):
            with self.service.lock("my-key"):
                pass

        self.redis_lock.release.assert_not_called()

    def test_proceeds_unlocked_when_redis_unavailable(self):
        self.connection.lock.side_effect = RedisConnectionError("redis down")
        entered = False

        with self.service.lock("my-key"):
            entered = True

        self.assertTrue(entered)
        self.redis_lock.release.assert_not_called()

    def test_release_failure_is_swallowed(self):
        self.redis_lock.acquire.return_value = True
        self.redis_lock.release.side_effect = RedisConnectionError("expired")

        with self.service.lock("my-key"):
            pass

        self.redis_lock.release.assert_called_once()

    @patch("connect.common.locks.get_redis_connection")
    def test_connection_lazily_resolved_from_django_redis(self, mock_get_connection):
        mock_get_connection.return_value = self.connection

        service = RedisLockService()

        self.assertIs(service.connection, self.connection)
        mock_get_connection.assert_called_once()
