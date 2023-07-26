from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from connect.internals.event_driven.producer.rabbitmq_publisher import RabbitmqPublisher
from connect.template_projects.models import TemplateType

@receiver(post_save, sender=TemplateType)
def create_template_type(sender, instance, created, **kwargs):
    if created:
        rabbitmq_publisher = RabbitmqPublisher()
        
        message_body = {
            "uuid": instance.uuid,
            "name": instance.name
        }        
        
        rabbitmq_publisher.send_message(message_body, exchange="template-types.topic", routing_key="")