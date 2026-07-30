import logging

from django.core.exceptions import ValidationError
from django.db import DatabaseError
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from weni.eda.django.consumers import EDAConsumer
from weni.eda.messages import Message

from connect.change_history.models import ChangeEvent


logger = logging.getLogger(__name__)


class ChangeEventConsumer(EDAConsumer):
    def consume(self, message: Message):
        body = message.json()

        try:
            ChangeEvent.objects.create(
                project_uuid=body.get("project_uuid"),
                user_email=body.get("user_email"),
                occurred_at=self._parse_occurred_at(body.get("date")),
                action=body.get("action"),
                entity=body.get("entity"),
                module=body.get("module"),
                object_id=body.get("object_id"),
                object_name=body.get("object_name"),
                old_value=body.get("old_value"),
                new_value=body.get("new_value"),
                user_ip=body.get("user_ip"),
            )
        except (TypeError, ValueError, ValidationError) as exception:
            logger.warning("Invalid change event discarded: %s", exception)
            self.ack()
            return
        except DatabaseError:
            logger.exception("Could not persist change event")
            raise

        self.ack()

    @staticmethod
    def _parse_occurred_at(raw_date):
        occurred_at = (
            parse_datetime(raw_date) if isinstance(raw_date, str) else raw_date
        )

        if occurred_at is None:
            raise ValueError(f"Invalid change event date: {raw_date!r}")

        if timezone.is_naive(occurred_at):
            occurred_at = timezone.make_aware(occurred_at, timezone.utc)

        return occurred_at
