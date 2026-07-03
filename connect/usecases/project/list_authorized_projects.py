import logging
from typing import Optional

from django.db.models import QuerySet

from connect.common.models import Project, ProjectRole

logger = logging.getLogger(__name__)


class ListAuthorizedProjectsUseCase:
    """List the projects a user is effectively authorized to access.

    Scopes the listing to the user's own authorizations so the serializer
    never authorizes foreign projects, which would raise
    ProjectAuthorizationException and surface as an HTTP 500.
    """

    def execute(self, user, organization_uuid: Optional[str] = None) -> QuerySet:
        # Keep both conditions in one filter() so the same ProjectAuthorization
        # row (the user's own) must match: NOT_SETTED grants no access.
        queryset = Project.objects.filter(
            project_authorizations__user=user,
            project_authorizations__role__gt=ProjectRole.NOT_SETTED.value,
        )

        if organization_uuid:
            queryset = queryset.filter(organization__uuid=organization_uuid)

        logger.info(f"Listing authorized projects for user={user.email}")
        return queryset
