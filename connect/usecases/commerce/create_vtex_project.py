import logging
from typing import Tuple

from django.conf import settings
from django.db import transaction

from connect.authentication.models import User
from connect.celery import app as celery_app
from connect.common.models import (
    BillingPlan,
    Organization,
    OrganizationRole,
    Project,
    TypeProject,
)
from connect.internals.event_driven.producer.rabbitmq_publisher import RabbitmqPublisher
from connect.usecases.authorizations.create import CreateAuthorizationUseCase
from connect.usecases.authorizations.dto import CreateAuthorizationDTO
from connect.usecases.commerce.dto import CreateVtexProjectDTO
from connect.usecases.commerce.eda_publisher import CommerceEDAPublisher
from connect.usecases.commerce.exceptions import ProjectAuthorizationMissingError
from connect.usecases.users.create import CreateKeycloakUserUseCase
from connect.usecases.users.user_dto import KeycloakUserDTO

logger = logging.getLogger(__name__)


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
            self._ensure_permissions(user, organization)

        logger.info(
            f"VTEX project ready project_uuid={project.uuid} "
            f"vtex_account={dto.vtex_account} created={project_created}"
        )
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

    def _ensure_permissions(self, user: User, organization: Organization) -> None:
        """Grant ADMIN org auth and project auth for every org project.

        Always calls CreateAuthorizationUseCase so retries republish auth
        events after a previous grant that rolled back on publish failure.
        """
        auth_dto = CreateAuthorizationDTO(
            user_email=user.email,
            org_uuid=str(organization.uuid),
            role=OrganizationRole.ADMIN.value,
        )
        CreateAuthorizationUseCase(
            message_publisher=self._auth_publisher(),
            publish_message=True,
        ).create_authorization(auth_dto)
        self._require_authorizations(user, organization)

    def _require_authorizations(self, user: User, organization: Organization) -> None:
        if not organization.authorizations.filter(user=user).exists():
            raise ProjectAuthorizationMissingError(
                f"OrganizationAuthorization missing after create "
                f"org_uuid={organization.uuid} user_email={user.email}"
            )
        for project in organization.project.all():
            if not project.project_authorizations.filter(user=user).exists():
                raise ProjectAuthorizationMissingError(
                    f"ProjectAuthorization missing after create "
                    f"project_uuid={project.uuid} user_email={user.email}"
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
