from connect.common.models import (
    Organization,
)
from connect.usecases.organizations.exceptions import OrganizationDoesNotExist


class RetrieveOrganizationUseCase:
    def get_organization_by_uuid(self, org_uuid: str) -> Organization:
        try:
            return Organization.objects.get(uuid=org_uuid)
        except Organization.DoesNotExist:
            raise OrganizationDoesNotExist(
                f"Organization with UUID: {org_uuid} Does Not Exist"
            )

    def get_organization_by_project_uuid(self, project_uuid: str) -> Organization:
        try:
            return Organization.objects.get(project__uuid=project_uuid)
        except Organization.DoesNotExist:
            raise OrganizationDoesNotExist(
                f"Organization with Project UUID: {project_uuid} Does Not Exist"
            )
