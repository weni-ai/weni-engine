import logging

from connect.common.models import Project
from connect.usecases.project.update_project import UpdateProjectUseCase

logger = logging.getLogger(__name__)


class SetVtexHostStoreUseCase:
    """Sets the vtex_host_store value in the project config and publishes an EDA update."""

    def __init__(self, update_project_usecase: UpdateProjectUseCase = None):
        self._update_project = update_project_usecase or UpdateProjectUseCase()

    def execute(self, project_uuid: str, vtex_host_store: str) -> dict:
        project = Project.objects.get(uuid=project_uuid)

        project.config["vtex_host_store"] = vtex_host_store
        project.save(update_fields=["config"])

        self._update_project.send_updated_project(project, user_email="")

        return {"project_uuid": str(project.uuid), "vtex_host_store": vtex_host_store}
