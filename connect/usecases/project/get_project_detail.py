import logging

from connect.common.models import Project
from connect.usecases.project.exceptions import ProjectNotFoundError

logger = logging.getLogger(__name__)


class GetProjectDetailUseCase:
    def execute(self, project_uuid: str) -> Project:
        project = self._get_project(project_uuid)
        logger.info(f"Retrieved project detail for project_uuid={project_uuid}")
        return project

    def _get_project(self, project_uuid: str) -> Project:
        try:
            return Project.objects.select_related(
                "organization__organization_billing"
            ).get(uuid=project_uuid)
        except Project.DoesNotExist:
            raise ProjectNotFoundError()
