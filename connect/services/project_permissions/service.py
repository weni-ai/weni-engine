from http import HTTPStatus
from typing import Dict, Optional, Tuple

from connect.usecases.authorizations.exceptions import (
    ProjectAuthorizationNotFoundError,
    UserNotFoundError,
)
from connect.usecases.authorizations.get_project_authorization import (
    GetProjectAuthorizationUseCase,
)


class ProjectUserPermissionsService:
    """Resolves project authorization levels from Connect's own database.

    Connect owns ``ProjectAuthorization``, so the level is read locally instead
    of calling the permissions endpoint over HTTP.
    """

    def __init__(
        self,
        get_authorization_usecase: Optional[GetProjectAuthorizationUseCase] = None,
    ):
        self.get_authorization_usecase = (
            get_authorization_usecase or GetProjectAuthorizationUseCase()
        )

    def get_user_permissions(
        self,
        project_uuid: str,
        user_email: str,
        user_token: Optional[str] = None,
    ) -> Tuple[int, Dict]:
        try:
            authorization = self.get_authorization_usecase.get_by_project_uuid(
                user_email=user_email,
                project_uuid=project_uuid,
            )
        except (UserNotFoundError, ProjectAuthorizationNotFoundError):
            return HTTPStatus.NOT_FOUND, {}

        return HTTPStatus.OK, {"project_authorization": authorization.role}
