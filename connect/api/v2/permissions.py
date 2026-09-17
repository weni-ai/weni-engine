from typing import Tuple

from weni_commons.auth import HasProjectPermission

from connect.common.models import ProjectRole
from connect.services.project_permissions.service import ProjectUserPermissionsService

PROJECT_ROLE_RANK = {
    ProjectRole.NOT_SETTED.value: 0,
    ProjectRole.CHAT_USER.value: 1,
    ProjectRole.VIEWER.value: 2,
    ProjectRole.MARKETING.value: 3,
    ProjectRole.CONTRIBUTOR.value: 4,
    ProjectRole.MODERATOR.value: 5,
    ProjectRole.SUPPORT.value: 6,
}


def roles_at_least(minimum_role: ProjectRole) -> Tuple[int, ...]:
    minimum_rank = PROJECT_ROLE_RANK[minimum_role.value]
    return tuple(
        role for role, rank in PROJECT_ROLE_RANK.items() if rank >= minimum_rank
    )


class BaseProjectRolePermission(HasProjectPermission):
    """Injects Connect's permissions service, since DRF instantiates
    permission classes with no arguments and the base class denies access
    when no service is set."""

    def __init__(self, permissions_service=None):
        super().__init__(permissions_service or ProjectUserPermissionsService())


class IsProjectViewer(BaseProjectRolePermission):
    ALLOWED_LEVELS = roles_at_least(ProjectRole.VIEWER)


class IsProjectContributor(BaseProjectRolePermission):
    ALLOWED_LEVELS = roles_at_least(ProjectRole.CONTRIBUTOR)


class IsProjectModerator(BaseProjectRolePermission):
    ALLOWED_LEVELS = roles_at_least(ProjectRole.MODERATOR)
