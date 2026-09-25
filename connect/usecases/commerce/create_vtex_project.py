import logging
from typing import NamedTuple, Optional, Tuple

from django.conf import settings
from django.db import transaction

from connect.authentication.models import User
from connect.celery import app as celery_app
from connect.common.models import (
    BillingPlan,
    Organization,
    OrganizationRole,
    Project,
    ProjectAuthorization,
    TypeProject,
)
from connect.internals.event_driven.producer.rabbitmq_publisher import RabbitmqPublisher
from connect.usecases.authorizations.create import CreateAuthorizationUseCase
from connect.usecases.authorizations.dto import CreateAuthorizationDTO
from connect.usecases.authorizations.usecase import AuthorizationUseCase
from connect.usecases.commerce.dto import CreateVtexProjectDTO
from connect.usecases.commerce.eda_publisher import CommerceEDAPublisher
from connect.usecases.commerce.exceptions import ProjectAuthorizationMissingError
from connect.usecases.users.create import CreateKeycloakUserUseCase
from connect.usecases.users.user_dto import KeycloakUserDTO

logger = logging.getLogger(__name__)


class _GrantedVtexAuthorization(NamedTuple):
    org_auth_action: str
    org_role: int
    project_role: int


class CreateVtexProjectUseCase:
    """Orchestrates the idempotent creation of a VTEX commerce project.

    Consolidates organization, project, user and permission setup
    into a single atomic operation with EDA event publishing.
    """

    def __init__(
        self,
        eda_publisher: CommerceEDAPublisher = None,
        auth_message_publisher=None,
    ):
        self._eda = eda_publisher or CommerceEDAPublisher()
        self._auth_message_publisher = auth_message_publisher

    def execute(self, dto: CreateVtexProjectDTO) -> dict:
        with transaction.atomic():
            user, user_created = self._get_or_create_user(
                dto.user_email, dto.organization_name
            )
            project, project_created = self._get_or_create_project(dto, user)
            organization = project.organization
            granted = self._ensure_permissions(user, project, organization)

        logger.info(
            f"VTEX project ready project_uuid={project.uuid} "
            f"vtex_account={dto.vtex_account} created={project_created}"
        )
        if granted:
            self._publish_authorization_events(user, project, organization, granted)
        self._notify_downstream_modules(organization, user, project)

        if project_created:
            self._send_request_flow_product(user)

        return {
            "project_uuid": str(project.uuid),
            "user_uuid": str(user.pk),
        }

    def _notify_downstream_modules(
        self, organization: Organization, user: User, project: Project
    ) -> None:
        """Publish org/project created even on idempotent retries.

        A previous attempt may have committed the project and then lost the
        RabbitMQ publish (stale connection). Downstream consumers upsert by uuid.
        """
        self._eda.publish_org_created(organization, user)
        self._eda.publish_project_created(project)

    def _get_or_create_user(
        self, email: str, company_name: str
    ) -> Tuple[User, bool]:
        try:
            return User.objects.get(email=email), False
        except User.DoesNotExist:
            user_dto = KeycloakUserDTO(email=email, company_name=company_name)
            user_info = CreateKeycloakUserUseCase(user_dto).execute()
            user = user_info["user"]
            user.send_email_access_password(user_info["password"])
            return user, True

    def _get_or_create_project(
        self, dto: CreateVtexProjectDTO, user: User
    ) -> Tuple[Project, bool]:
        try:
            project = Project.objects.get(vtex_account=dto.vtex_account)
            if project.language != dto.language:
                project.language = dto.language
                project.save(update_fields=["language"])
            return project, False
        except Project.DoesNotExist:
            pass
        except Project.MultipleObjectsReturned:
            raise ValueError(
                f"Multiple projects found for vtex_account '{dto.vtex_account}'. "
                "Expected exactly one."
            )

        organization = self._create_organization(dto.organization_name)
        project = Project.objects.create(
            name=dto.project_name,
            vtex_account=dto.vtex_account,
            timezone="America/Sao_Paulo",
            organization=organization,
            created_by=user,
            is_template=False,
            project_type=TypeProject.COMMERCE,
            language=dto.language,
        )
        return project, True

    def _create_organization(self, organization_name: str) -> Organization:
        return Organization.objects.create(
            name=organization_name,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
            description=f"Organization {organization_name}",
            organization_billing__cycle=BillingPlan._meta.get_field("cycle").default,
        )

    def _ensure_permissions(
        self, user: User, project: Project, organization: Organization
    ) -> Optional[_GrantedVtexAuthorization]:
        """Grant ADMIN org auth and project auth in the same transaction.

        Returns publish payload when membership was written here, or None when
        ProjectAuthorization already existed so auth events are not republished.
        RabbitMQ is left to the caller after commit.
        """
        if ProjectAuthorization.objects.filter(project=project, user=user).exists():
            return None

        org_auth_existed = organization.authorizations.filter(user=user).exists()
        auth_dto = CreateAuthorizationDTO(
            user_email=user.email,
            org_uuid=str(organization.uuid),
            role=OrganizationRole.ADMIN.value,
        )
        CreateAuthorizationUseCase(
            message_publisher=self._auth_publisher(),
            publish_message=False,
        ).create_authorization(auth_dto)

        return _GrantedVtexAuthorization(
            org_auth_action="update" if org_auth_existed else "create",
            org_role=self._required_org_auth_role(organization, user),
            project_role=self._required_project_auth_role(project, user),
        )

    def _required_org_auth_role(self, organization: Organization, user: User) -> int:
        org_auth = organization.authorizations.filter(user=user).first()
        if org_auth is None:
            raise ProjectAuthorizationMissingError(
                f"OrganizationAuthorization missing after create "
                f"org_uuid={organization.uuid} user_email={user.email}"
            )
        return org_auth.role

    def _required_project_auth_role(self, project: Project, user: User) -> int:
        project_auth = project.project_authorizations.filter(user=user).first()
        if project_auth is None:
            raise ProjectAuthorizationMissingError(
                f"ProjectAuthorization missing after create "
                f"project_uuid={project.uuid} user_email={user.email}"
            )
        return project_auth.role

    def _publish_authorization_events(
        self,
        user: User,
        project: Project,
        organization: Organization,
        granted: _GrantedVtexAuthorization,
    ) -> None:
        publisher = AuthorizationUseCase(
            message_publisher=self._auth_publisher(),
            publish_message=True,
        )
        publisher.publish_organization_authorization_message(
            action=granted.org_auth_action,
            org_uuid=str(organization.uuid),
            user_email=user.email,
            role=granted.org_role,
            org_intelligence=organization.inteligence_organization,
        )
        publisher.publish_project_authorization_message(
            action="create",
            project_uuid=str(project.uuid),
            user_email=user.email,
            role=granted.project_role,
        )

    def _auth_publisher(self):
        return self._auth_message_publisher or RabbitmqPublisher()

    @staticmethod
    def _send_request_flow_product(user: User) -> None:
        if Project.objects.filter(created_by=user).count() == 1:
            data = {
                "send_request_flow": settings.SEND_REQUEST_FLOW_PRODUCT,
                "flow_uuid": settings.FLOW_PRODUCT_UUID,
                "token_authorization": settings.TOKEN_AUTHORIZATION_FLOW_PRODUCT,
            }
            celery_app.send_task("send_user_flow_info", args=[data, user.email])
