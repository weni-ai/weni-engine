import uuid

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings

from connect.internals.event_driven.producer.rabbitmq_publisher import RabbitmqPublisher
from connect.template_projects.models import TemplateType


@receiver(post_save, sender=TemplateType)
def create_template_type(sender, instance, created, **kwargs):
    if created and not settings.TESTING:
        rabbitmq_publisher = RabbitmqPublisher()
        if instance.uuid is None:
            instance.uuid = uuid.uuid4()
            instance.save()

        message_body = {
            "uuid": str(instance.uuid),
            "name": instance.name,
            "project_uuid": str(instance.base_project_uuid)
        }

        rabbitmq_publisher.send_message(message_body, exchange="template-types.topic", routing_key="")
