import logging

from connect.common.models import Project
from connect.usecases.project.update_project import UpdateProjectUseCase

logger = logging.getLogger(__name__)


class UpdateProjectConfigUseCase:
    """Merges the given keys into the project config and publishes an EDA update."""

    def __init__(self, update_project_usecase: UpdateProjectUseCase = None):
        self._update_project = update_project_usecase or UpdateProjectUseCase()

    def execute(self, project_uuid: str, config: dict) -> dict:
        project = Project.objects.get(uuid=project_uuid)

        project.config.update(config)
        project.save(update_fields=["config"])

        self._update_project.send_updated_project(project, user_email="")

        return {"project_uuid": str(project.uuid), "config": project.config}
