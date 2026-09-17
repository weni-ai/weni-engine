from uuid import uuid4

from django.db import models

from weni_commons.change_history import Action, Entity, Module


class ChangeEvent(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    project_uuid = models.UUIDField()
    user_email = models.EmailField()
    occurred_at = models.DateTimeField()

    action = models.CharField(max_length=32, choices=Action.to_choices())
    entity = models.CharField(max_length=32, choices=Entity.to_choices())
    module = models.CharField(max_length=32, choices=Module.to_choices())

    object_id = models.CharField(max_length=255, null=True, blank=True)
    object_name = models.CharField(max_length=255, null=True, blank=True)
    old_value = models.TextField(null=True, blank=True)
    new_value = models.TextField(null=True, blank=True)
    user_ip = models.GenericIPAddressField(null=True, blank=True)

    def __str__(self):
        return f"{self.user_email}/{self.project_uuid} | {self.action} - {self.entity}"
