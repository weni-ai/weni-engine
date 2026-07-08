from typing import List

from django.contrib.auth import get_user_model
from django.db.models import Count, Q

from connect.common.models import (
    Organization,
    OrganizationAuthorization,
    OrganizationRole,
)

User = get_user_model()


class ListOrgsByUserUseCase:
    """Lists the organizations a user belongs to, including their projects
    and the active member count of each organization.

    The lookup is performed by email so it can be consumed by internal
    services that only hold the user's email.
    """

    _EXCLUDED_ROLES = [OrganizationRole.NOT_SETTED.value]

    def execute(self, user_email: str) -> List[dict]:
        try:
            user = User.objects.get(email=user_email)
        except User.DoesNotExist:
            return []

        organization_ids = (
            OrganizationAuthorization.objects.filter(user=user)
            .exclude(role__in=self._EXCLUDED_ROLES)
            .values_list("organization", flat=True)
        )
        organizations = (
            Organization.objects.filter(pk__in=organization_ids)
            .prefetch_related("project")
            .annotate(
                member_count=Count(
                    "authorizations",
                    filter=~Q(authorizations__role__in=self._EXCLUDED_ROLES),
                )
            )
        )

        return [self._serialize_organization(org) for org in organizations]

    def _serialize_organization(self, organization: Organization) -> dict:
        return {
            "uuid": str(organization.uuid),
            "name": organization.name,
            "member_count": organization.member_count,
            "projects": [
                {"uuid": str(project.uuid), "name": project.name}
                for project in organization.project.all()
            ],
        }
