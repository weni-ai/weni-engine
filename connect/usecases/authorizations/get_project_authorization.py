import logging

from connect.common.models import Project, ProjectAuthorization, User
from connect.usecases.authorizations.exceptions import (
    MultipleProjectsForVtexAccountError,
    ProjectAuthorizationNotFoundError,
    UserNotFoundError,
)
from connect.usecases.project.exceptions import ProjectNotFoundError

logger = logging.getLogger(__name__)


class GetProjectAuthorizationUseCase:
    def get_by_project_uuid(
        self, user_email: str, project_uuid: str
    ) -> ProjectAuthorization:
        user = self._get_user(user_email)
        authorization = self._get_authorization(user, project__uuid=project_uuid)
        logger.info(
            f"Retrieved project authorization for user={user_email} "
            f"project_uuid={project_uuid}"
        )
        return authorization

    def get_by_vtex_account(
        self, user_email: str, vtex_account: str
    ) -> ProjectAuthorization:
        user = self._get_user(user_email)
        project = self._get_project_by_vtex_account(vtex_account)
        authorization = self._get_authorization(user, project=project)
        logger.info(
            f"Retrieved project authorization for user={user_email} "
            f"vtex_account={vtex_account}"
        )
        return authorization

    def _get_user(self, email: str) -> User:
        try:
            return User.objects.get(email=email)
        except User.DoesNotExist:
            raise UserNotFoundError()

    def _get_project_by_vtex_account(self, vtex_account: str) -> Project:
        try:
            return Project.objects.get(vtex_account=vtex_account)
        except Project.DoesNotExist:
            raise ProjectNotFoundError()
        except Project.MultipleObjectsReturned:
            raise MultipleProjectsForVtexAccountError()

    def _get_authorization(self, user: User, **filters) -> ProjectAuthorization:
        try:
            return user.project_authorizations_user.get(**filters)
        except ProjectAuthorization.DoesNotExist:
            raise ProjectAuthorizationNotFoundError()
