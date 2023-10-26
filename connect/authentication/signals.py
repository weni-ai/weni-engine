import logging

from django.conf import settings
from django.db import models
from django.dispatch import receiver

from connect.api.v1.keycloak import KeycloakControl
from connect.authentication.models import User

logger = logging.getLogger("connect.authentication.signals")


@receiver(models.signals.post_save, sender=User)
def signal_user(instance, created, **kwargs):

    if created:
        from connect.common.models import (
            RequestPermissionOrganization,
            RequestPermissionProject,
        )

        requests_perm = RequestPermissionOrganization.objects.filter(
            email=instance.email
        )
        for perm in requests_perm:
            perm.organization.get_user_authorization(
                user=instance, defaults={"role": perm.role}
            )
        requests_perm.delete()

        requests_perm_project = RequestPermissionProject.objects.filter(
            email=instance.email
        )
        for perm in requests_perm_project:
            perm.project.get_user_authorization(
                user=instance, defaults={"role": perm.role}
            )
        requests_perm_project.delete()


@receiver(models.signals.post_delete, sender=User)
def delete_user(instance, **kwargs):
    if settings.TESTING:
        return False  # pragma: no cover
    keycloak_instance = KeycloakControl()
    user_id = keycloak_instance.get_user_id_by_email(email=instance.email)
    keycloak_instance.delete_user(user_id=user_id)
