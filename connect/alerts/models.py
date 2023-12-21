import uuid as uuid4
from django.db import models


class Alert(models.Model):

    alert_types = [
        (1, "very_high"),
        (2, "high"),
        (3, "medium"),
        (4, "low"),
        (5, "very_low"),
    ]

    can_be_closed = models.BooleanField()
    text = models.TextField()
    type = models.IntegerField(choices=alert_types)
    uuid = models.UUIDField(default=uuid4.uuid4)
    created_at = models.DateTimeField(auto_now_add=True)
