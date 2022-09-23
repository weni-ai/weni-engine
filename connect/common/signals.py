import logging

from django.conf import settings
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone

from connect.authentication.models import User
from connect.common.models import (
    ChatsAuthorization,
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
)
from connect.celery import app as celery_app
from connect.api.v1.internal.intelligence.intelligence_rest_client import IntelligenceRESTClient
from connect.api.v1.internal.chats.chats_rest_client import ChatsRESTClient

logger = logging.getLogger("connect.common.signals")


@receiver(post_save, sender=Project)
def create_service_status(sender, instance, created, **kwargs):
    if created:
        for service in Service.objects.filter(default=True):
            instance.service_status.create(service=service)
        if not settings.TESTING:
            logger.info('creating chats_project')
            chats_client = ChatsRESTClient()
            response = chats_client.create_chat_project(
                project_uuid=str(instance.uuid),
                project_name=instance.name,
                date_format=instance.date_format,
                timezone=str(instance.timezone),
                is_template=instance.is_template
            )
            logger.info(f'[ * ] {response}')

        for permission in instance.project_authorizations.all():
            celery_app.send_task(
                "update_user_permission_project",
                args=[
                    instance.flow_organization,
                    instance.uuid,
                    permission.user.email,
                    permission.role,
                ],
            )
        for authorization in instance.organization.authorizations.all():
            if authorization.can_contribute:
                project_auth = instance.get_user_authorization(authorization.user)
                project_auth.role = authorization.role
                project_auth.save()


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
                str(project.flow_organization),
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
        # todo: send invite project email


@receiver(post_save, sender=ProjectAuthorization)
def project_authorization(sender, instance, created, **kwargs):
    if created:
        if not settings.TESTING and instance.is_moderator and not instance.chats_authorization:
            RequestChatsPermission.objects.create(
                email=instance.user.email,
                role=ChatsRole.ADMIN.value,
                project=instance.project,
                created_by=instance.user
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

        celery_app.send_task(
            "update_user_permission_project",
            args=[
                instance.project.flow_organization,
                instance.project.uuid,
                instance.user.email,
                instance.role,
            ],
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
                chats_role = ChatsRole.ADMIN.value if project_auth.is_moderator else instance.role
                if not project_auth.chats_authorization:
                    project_auth.chats_authorization = ChatsAuthorization.objects.create(role=chats_role)
                    if not settings.TESTING:
                        chats_instance.create_user_permission(
                            project_uuid=str(instance.project.uuid),
                            user_email=user.email,
                            permission=chats_role
                        )
                else:
                    project_auth.chats_authorization.role = chats_role
                    project_auth.chats_authorization.save(update_fields=["role"])
                    if not settings.TESTING:
                        chats_instance.update_user_permission(
                            permission=chats_role,
                            user_email=user.email,
                            project_uuid=str(instance.project_uuid)
                        )
                project_auth.save(update_fields=["chats_authorization"])
                instance.delete()
