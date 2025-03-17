import logging

from django.conf import settings
from django.db import models
from django.dispatch import receiver

from connect.api.v1.keycloak import KeycloakControl
from connect.authentication.models import User

from connect.usecases.authorizations.create import CreateAuthorizationUseCase
from connect.usecases.authorizations.dto import (
    CreateAuthorizationDTO,
    CreateProjectAuthorizationDTO,
)
from connect.internals.event_driven.producer.rabbitmq_publisher import RabbitmqPublisher


logger = logging.getLogger("connect.authentication.signals")


@receiver(models.signals.post_save, sender=User)
def signal_user(instance, created, **kwargs):
    from connect.common.models import (
        RequestPermissionOrganization,
        RequestPermissionProject,
    )

    if settings.USE_EDA_PERMISSIONS and created:
        requests_permission_organizations = (
            RequestPermissionOrganization.objects.filter(email=instance.email)
        )
        requests_permission_projects = RequestPermissionProject.objects.filter(
            email=instance.email
        )
        rabbitmq_publisher = RabbitmqPublisher()
        usecase = CreateAuthorizationUseCase(rabbitmq_publisher)

        for requests_permission_organization in requests_permission_organizations:
            auth_dto = CreateAuthorizationDTO(
                user_email=requests_permission_organization.email,
                org_uuid=str(requests_permission_organization.organization.uuid),
                role=requests_permission_organization.role,
            )
            usecase.create_authorization(auth_dto)
            requests_permission_organization.delete()

        for requests_permission_project in requests_permission_projects:
            auth_dto = CreateProjectAuthorizationDTO(
                user_email=requests_permission_project.email,
                project_uuid=str(requests_permission_project.project.uuid),
                role=requests_permission_project.role,
                created_by_email=requests_permission_project.created_by.email,
            )
            usecase.create_authorization_for_a_single_project(auth_dto=auth_dto)
            requests_permission_project.delete()

        return


@receiver(models.signals.post_delete, sender=User)
def delete_user(instance, **kwargs):
    if settings.TESTING:
        return False  # pragma: no cover
    keycloak_instance = KeycloakControl()
    user_id = keycloak_instance.get_user_id_by_email(email=instance.email)
    keycloak_instance.delete_user(user_id=user_id)
