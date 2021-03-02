import logging

from django.conf import settings
from django.db import models
from django.dispatch import receiver
from django.utils.translation import ugettext_lazy as _
from keycloak import exceptions
from rest_framework.exceptions import ValidationError

from weni.api.v1.keycloak import KeycloakControl
from weni.authentication.models import User


logger = logging.getLogger("weni.authentication.signals")


@receiver(models.signals.post_save, sender=User)
def update_user_keycloak(instance, **kwargs):
    if not settings.TESTING:
        try:
            keycloak_instance = KeycloakControl()

            user_id = keycloak_instance.get_user_id_by_email(email=instance.email)
            keycloak_instance.get_instance().update_user(
                user_id=user_id,
                payload={
                    "firstName": instance.first_name,
                    "lastName": instance.last_name,
                },
            )
        except exceptions.KeycloakGetError as e:
            logger.error(e)
            # raise ValidationError(
            #     _("System temporarily unavailable, please try again later.")
            # )
