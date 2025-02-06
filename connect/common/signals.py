import logging

from django.conf import settings
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone

from connect.authentication.models import User
from connect.common.models import (
    ChatsRole,
    Project,
    Service,
    Organization,
    RequestPermissionOrganization,
    ProjectAuthorization,
    RocketAuthorization,
    RequestRocketPermission,
    RequestChatsPermission,
    OpenedProject,
)
from connect.celery import app as celery_app
from connect.api.v1.internal.chats.chats_rest_client import ChatsRESTClient
from connect.common.tasks import update_user_permission_project

from connect.usecases.authorizations.create import CreateAuthorizationUseCase
from connect.usecases.authorizations.dto import CreateAuthorizationDTO
from connect.internals.event_driven.producer.rabbitmq_publisher import RabbitmqPublisher


logger = logging.getLogger("connect.common.signals")


@receiver(post_save, sender=Project)
def create_service_status(sender, instance, created, **kwargs):
    update_fields = (
        list(kwargs.get("update_fields")) if kwargs.get("update_fields") else None
    )
    if created:
        for service in Service.objects.filter(default=True):
            instance.service_status.create(service=service)
        if not settings.TESTING:

            if len(Project.objects.filter(created_by=instance.created_by)) == 1:
                data = dict(
                    send_request_flow=settings.SEND_REQUEST_FLOW_PRODUCT,
                    flow_uuid=settings.FLOW_PRODUCT_UUID,
                    token_authorization=settings.TOKEN_AUTHORIZATION_FLOW_PRODUCT,
                )
                instance.created_by.send_request_flow_user_info(data)

        if instance.flow_organization:
            for permission in instance.project_authorizations.all():
                update_user_permission_project(
                    project_uuid=str(instance.uuid),
                    flow_organization=str(instance.flow_organization),
                    user_email=permission.user.email,
                    permission=permission.role,
                )

        for authorization in instance.organization.authorizations.all():
            if authorization.can_contribute:
                project_auth = instance.get_user_authorization(authorization.user)
                project_auth.role = authorization.role
                project_auth.save()

    elif update_fields and "flow_organization" in update_fields:
        for permission in instance.project_authorizations.all():
            update_user_permission_project(
                project_uuid=str(instance.uuid),
                flow_organization=str(instance.flow_organization),
                user_email=permission.user.email,
                permission=permission.role,
            )


@receiver(post_save, sender=Service)
def create_service_default_in_all_user(sender, instance, created, **kwargs):
    if created and instance.default:
        for project in Project.objects.all():
            project.service_status.create(service=instance)


@receiver(post_save, sender=Organization)
def update_organization(instance, **kwargs):
    for project in instance.project.all():
        celery_app.send_task(  # pragma: no cover
            name="update_suspend_project",
            args=[
                str(project.uuid),
                instance.is_suspended,
            ],
        )


@receiver(post_delete, sender=ProjectAuthorization)
def delete_opened_project(sender, instance, **kwargs):
    opened = OpenedProject.objects.filter(user=instance.user, project=instance.project)
    if opened.exists():
        opened.delete()


@receiver(post_save, sender=RequestPermissionOrganization)
def request_permission_organization(sender, instance, created, **kwargs):
    if created:
        user = User.objects.filter(email=instance.email)
        if user.exists():
            auth_dto = CreateAuthorizationDTO(
                user_email=instance.email,
                org_uuid=str(instance.organization.uuid),
                role=instance.role,
            )
            rabbitmq_publisher = RabbitmqPublisher()
            usecase = CreateAuthorizationUseCase(rabbitmq_publisher)
            usecase.create_authorization(auth_dto)
            instance.delete()
        instance.organization.send_email_invite_organization(email=instance.email)
    return


@receiver(post_save, sender=ProjectAuthorization)
def project_authorization(sender, instance, created, **kwargs):
    opened = OpenedProject.objects.filter(project=instance.project, user=instance.user)
    if not opened.exists():
        OpenedProject.objects.create(
            user=instance.user,
            project=instance.project,
            day=instance.project.created_at,
        )
        opened = opened.first()
        opened.day = timezone.now()
        opened.save()
    return


@receiver(post_save, sender=RequestRocketPermission)
def request_rocket_permission(sender, instance, created, **kwargs):
    if created:
        user = User.objects.filter(email=instance.email)
        if user.exists():
            user = user.first()
            project_auth = instance.project.project_authorizations.filter(user=user)
            if project_auth.exists():
                project_auth = project_auth.first()
                if not project_auth.rocket_authorization:
                    project_auth.rocket_authorization = (
                        RocketAuthorization.objects.create(role=instance.role)
                    )
                else:
                    project_auth.rocket_authorization.role = instance.role
                project_auth.save(update_fields=["rocket_authorization"])
                project_auth.rocket_authorization.update_rocket_permission()
            instance.delete()


@receiver(post_save, sender=RequestChatsPermission)
def request_chats_permission(sender, instance, created, **kwargs):
    if created:
        user = User.objects.filter(email=instance.email)
        if user.exists():
            user = user.first()
            project_auth = instance.project.project_authorizations.filter(user=user)
            chats_instance = ChatsRESTClient()
            if project_auth.exists():
                project_auth = project_auth.first()
                chats_role = (
                    ChatsRole.ADMIN.value
                    if project_auth.is_moderator
                    else ChatsRole.AGENT.value
                )
                if not project_auth.chats_authorization:
                    if not settings.TESTING:
                        chats_instance.update_user_permission(
                            project_uuid=str(instance.project.uuid),
                            user_email=user.email,
                            permission=chats_role,
                        )
                else:
                    # project_auth.chats_authorization.role = chats_role
                    # project_auth.chats_authorization.save(update_fields=["role"])
                    if not settings.TESTING:
                        chats_instance.update_user_permission(
                            permission=chats_role,
                            user_email=user.email,
                            project_uuid=str(instance.project.uuid),
                        )
                # project_auth.save(update_fields=["chats_authorization"])
                instance.delete()


@receiver(post_save, sender=Project)
def send_email_create_project(sender, instance, created, **kwargs):
    if created and not instance.vtex_account:
        instance.send_email_create_project()
