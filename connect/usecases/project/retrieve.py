from connect.common.models import (
    Project,
)
from connect.usecases.project.exceptions import ProjectDoesNotExist


class RetrieveProjectUseCase:
    def get_project_by_uuid(self, project_uuid: str) -> Project:
        try:
            return Project.objects.get(uuid=project_uuid)
        except Project.DoesNotExist:
            raise ProjectDoesNotExist(f"Project with UUID: {project_uuid} Does Not Exist")
