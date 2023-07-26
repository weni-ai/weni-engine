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
    OrganizationAuthorization,
    RequestPermissionOrganization,
    OrganizationLevelRole,
    OrganizationRole,
    RequestPermissionProject,
    ProjectAuthorization,
    ProjectRole,
    ProjectRoleLevel,
    RocketAuthorization,
    RequestRocketPermission,
    RequestChatsPermission,
    OpenedProject,
    RecentActivity
)
from connect.celery import app as celery_app
from connect.api.v1.internal.intelligence.intelligence_rest_client import IntelligenceRESTClient
from connect.api.v1.internal.chats.chats_rest_client import ChatsRESTClient
from connect.common.tasks import update_user_permission_project
from connect.internals.event_driven.producer.rabbitmq_publisher import RabbitmqPublisher
from requests.exceptions import HTTPError
from rest_framework.exceptions import APIException


logger = logging.getLogger("connect.common.signals")


@receiver(post_save, sender=Project)
def create_service_status(sender, instance, created, **kwargs):
    update_fields = list(kwargs.get("update_fields")) if kwargs.get("update_fields") else None
    if created:
        for service in Service.objects.filter(default=True):
            instance.service_status.create(service=service)
        if not settings.TESTING:
            chats_client = ChatsRESTClient()
            ai_client = IntelligenceRESTClient()

            template = instance.is_template and instance.template_type in Project.HAS_CHATS

            try:
                ai_client.create_project(instance.uuid)
            except HTTPError as e:
                raise APIException(e)

            if not template:
                response = chats_client.create_chat_project(
                    project_uuid=str(instance.uuid),
                    project_name=instance.name,
                    date_format=instance.date_format,
                    timezone=str(instance.timezone),
                    is_template=template,
                    user_email=instance.created_by.email
                )
                logger.info(f'[ * ] {response}')

            if len(Project.objects.filter(created_by=instance.created_by)) == 1:
                data = dict(
                    send_request_flow=settings.SEND_REQUEST_FLOW_PRODUCT,
                    flow_uuid=settings.FLOW_PRODUCT_UUID,
                    token_authorization=settings.TOKEN_AUTHORIZATION_FLOW_PRODUCT
                )
                instance.created_by.send_request_flow_user_info(data)

        if instance.flow_organization:
            for permission in instance.project_authorizations.all():
                update_user_permission_project(
                    project_uuid=str(instance.uuid),
                    flow_organization=str(instance.flow_organization),
                    user_email=permission.user.email,
                    permission=permission.role
                )

        for authorization in instance.organization.authorizations.all():
            if authorization.can_contribute:
                project_auth = instance.get_user_authorization(authorization.user)
                project_auth.role = authorization.role
                project_auth.save()
                if not settings.TESTING and project_auth.is_moderator:
                    RequestChatsPermission.objects.create(
                        email=project_auth.user.email,
                        role=ChatsRole.ADMIN.value,
                        project=project_auth.project,
                        created_by=project_auth.user
                    )
    elif update_fields and "flow_organization" in update_fields:
        for permission in instance.project_authorizations.all():
            update_user_permission_project(
                project_uuid=str(instance.uuid),
                flow_organization=str(instance.flow_organization),
                user_email=permission.user.email,
                permission=permission.role
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


@receiver(post_save, sender=OrganizationAuthorization)
def org_authorizations(sender, instance, created, **kwargs):
    # if settings.CREATE_AI_ORGANIZATION:
    if instance.role is not OrganizationLevelRole.NOTHING.value:
        if created:
            organization_permission_mapper = {
                OrganizationRole.ADMIN.value: ProjectRole.MODERATOR.value,
                OrganizationRole.CONTRIBUTOR.value: ProjectRole.CONTRIBUTOR.value,
                OrganizationRole.SUPPORT.value: ProjectRole.SUPPORT.value,
            }
            for project in instance.organization.project.all():
                project_perm = project.project_authorizations.filter(user=instance.user)
                project_role = organization_permission_mapper.get(instance.role, ProjectRole.NOT_SETTED.value)
                if not project_perm.exists():
                    project.project_authorizations.create(
                        user=instance.user,
                        role=project_role,
                        organization_authorization=instance,
                    )
                else:
                    project_perm = project_perm.first()
                    if instance.role > project_perm.role:
                        project_perm.role = project_role
                        project_perm.save(update_fields=["role"])
        if not settings.TESTING:
            ai_client = IntelligenceRESTClient()
            ai_client.update_user_permission_organization(
                organization_id=instance.organization.inteligence_organization,
                user_email=instance.user.email,
                permission=instance.role
            )


@receiver(post_delete, sender=OrganizationAuthorization)
def delete_authorizations(instance, **kwargs):
    for project in instance.organization.project.all():
        project.project_authorizations.filter(user__email=instance.user.email).delete()

    if not settings.TESTING:
        ai_client = IntelligenceRESTClient()
        ai_client.delete_user_permission(
            organization_id=instance.organization.inteligence_organization,
            user_email=instance.user.email
        )

    instance.organization.send_email_remove_permission_organization(
        first_name=instance.user.first_name, email=instance.user.email
    )


@receiver(post_save, sender=RequestPermissionOrganization)
def request_permission_organization(sender, instance, created, **kwargs):
    if created:
        user = User.objects.filter(email=instance.email)
        if user.exists():
            user = user.first()
            perm = instance.organization.get_user_authorization(user=user)
            perm.role = instance.role
            update_fields = ["role"]
            if user.has_2fa:
                perm.has_2fa = True
                update_fields.append("has_2fa")
            perm.save(update_fields=update_fields)
            if perm.can_contribute:
                organization_permission_mapper = {
                    OrganizationRole.ADMIN.value: ProjectRole.MODERATOR.value,
                    OrganizationRole.CONTRIBUTOR.value: ProjectRole.CONTRIBUTOR.value,
                    OrganizationRole.SUPPORT.value: ProjectRole.SUPPORT.value,
                }
                for proj in instance.organization.project.all():
                    project_perm = proj.project_authorizations.filter(user=user)
                    project_role = organization_permission_mapper.get(perm.role, None)
                    if not project_perm.exists() and project_role is not None:
                        proj.project_authorizations.create(
                            user=user,
                            role=project_role,
                            organization_authorization=perm,
                        )
                    else:
                        project_perm = project_perm.first()
                        project_role = organization_permission_mapper.get(perm.role, None)
                        if project_perm.role < perm.role and project_role is not None:
                            project_perm.role = project_role
                            project_perm.save()
            instance.delete()
        instance.organization.send_email_invite_organization(email=instance.email)


@receiver(post_save, sender=RequestPermissionProject)
def request_permission_project(sender, instance, created, **kwargs):
    if created:
        user = User.objects.filter(email=instance.email)
        if user.exists():
            user = user.first()
            org = instance.project.organization
            org_auth = org.authorizations.filter(user__email=user.email)

            if not org_auth.exists():
                org_auth = org.authorizations.create(
                    user=user, role=OrganizationRole.VIEWER.value
                )
            else:
                org_auth = org_auth.first()

            auth = instance.project.project_authorizations
            auth_user = auth.filter(user=user)
            if not auth_user.exists():
                auth_user = ProjectAuthorization.objects.create(
                    user=user,
                    project=instance.project,
                    organization_authorization=org_auth,
                    role=instance.role,
                )
            else:
                auth_user = auth_user.first()
                auth_user.role = instance.role
                auth_user.save(update_fields=["role"])

            if not settings.TESTING and auth_user.is_moderator:
                RequestChatsPermission.objects.create(
                    email=instance.email,
                    role=ChatsRole.ADMIN.value,
                    project=instance.project,
                    created_by=instance.created_by
                )
            instance.delete()
        instance.project.send_email_invite_project(email=instance.email)


@receiver(post_save, sender=ProjectAuthorization)
def project_authorization(sender, instance, created, **kwargs):
    if created:
        if instance.is_moderator:
            RequestChatsPermission.objects.create(
                email=instance.user.email,
                role=ChatsRole.ADMIN.value,
                project=instance.project,
                created_by=instance.user
            )
        else:
            RequestChatsPermission.objects.create(
                email=instance.user.email,
                role=ChatsRole.AGENT.value,
                project=instance.project,
                created_by=instance.user
            )

        RecentActivity.objects.create(
            action="ADD",
            entity="USER",
            user=instance.user,
            project=instance.project,
            entity_name=instance.project.name
        )
    if instance.role is not ProjectRoleLevel.NOTHING.value:
        instance_user = (
            instance.organization_authorization.organization.get_user_authorization(
                instance.user
            )
        )
        opened = OpenedProject.objects.filter(project=instance.project, user=instance.user)
        if not opened.exists():
            OpenedProject.objects.create(
                user=instance.user,
                project=instance.project,
                day=instance.project.created_at
            )
        else:
            opened = opened.first()
            opened.day = timezone.now()
            opened.save()
        if instance_user.level == OrganizationLevelRole.NOTHING.value:
            instance_user.role = OrganizationRole.VIEWER.value
            instance_user.save(update_fields=["role"])
        if instance.project.flow_organization:
            update_user_permission_project(
                project_uuid=str(instance.project.uuid),
                flow_organization=str(instance.project.flow_organization),
                user_email=instance.user.email,
                permission=instance.role
            )


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
                chats_role = ChatsRole.ADMIN.value if project_auth.is_moderator else ChatsRole.AGENT.value
                if not project_auth.chats_authorization:
                    if not settings.TESTING:
                        chats_instance.update_user_permission(
                            project_uuid=str(instance.project.uuid),
                            user_email=user.email,
                            permission=chats_role
                        )
                else:
                    # project_auth.chats_authorization.role = chats_role
                    # project_auth.chats_authorization.save(update_fields=["role"])
                    if not settings.TESTING:
                        chats_instance.update_user_permission(
                            permission=chats_role,
                            user_email=user.email,
                            project_uuid=str(instance.project.uuid)
                        )
                # project_auth.save(update_fields=["chats_authorization"])
                instance.delete()


@receiver(post_save, sender=Project)
def send_email_create_project(sender, instance, created, **kwargs):
    if created:
        instance.send_email_create_project()

        message_body = {
            "uuid": str(instance.uuid),
            "name": instance.name,
            "is_template": instance.is_template,
            "user_email": instance.created_by.email if instance.created_by else None,
            "date_format": instance.date_format,
            "template_type_uuid": instance.project_template_type.uuid if instance.project_template_type else None,
            "timezone": str(instance.timezone)
        }

        rabbitmq_publisher = RabbitmqPublisher()
        rabbitmq_publisher.send_message(message_body, exchange="projects.topic", routing_key="")
