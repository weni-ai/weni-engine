import logging

from connect.api.v1.internal.insights.insights_rest_client import InsightsRESTClient
from connect.common.models import Project
from connect.usecases.commerce.exceptions import (
    ProjectAlreadyHasVtexAccountError,
    VtexAccountAlreadyLinkedError,
)

logger = logging.getLogger(__name__)


class LinkVtexAccountUseCase:
    """Links a vtex_account to an existing project at the root (Connect).

    Connect is the source of truth for the vtex_account uniqueness rules, so
    both validations happen here:
        1. The target project must not already have a vtex_account.
        2. The vtex_account must not be linked to any other project.

    After persisting the link, Insights is notified about the migration.
    """

    def __init__(self, insights_client: InsightsRESTClient = None):
        self._insights = insights_client or InsightsRESTClient()

    def execute(self, project_uuid: str, vtex_account: str) -> dict:
        project = Project.objects.get(uuid=project_uuid)
        self._validate(project, vtex_account)

        project.vtex_account = vtex_account
        project.save(update_fields=["vtex_account"])
        logger.info(
            f"Linked vtex_account={vtex_account} to project={project.uuid}"
        )

        self._notify_insights(project)

        return {"success": True}

    def _validate(self, project: Project, vtex_account: str) -> None:
        if project.vtex_account:
            raise ProjectAlreadyHasVtexAccountError(
                f"Project {project.uuid} already has a vtex_account linked."
            )

        already_linked = (
            Project.objects.filter(vtex_account=vtex_account)
            .exclude(uuid=project.uuid)
            .exists()
        )
        if already_linked:
            raise VtexAccountAlreadyLinkedError(
                f"vtex_account '{vtex_account}' is already linked to "
                "another project."
            )

    def _notify_insights(self, project: Project) -> None:
        """Best-effort notification to Insights.

        The Insights endpoint is still temporary, so failures here must not
        roll back the vtex_account link already persisted in Connect.
        """
        try:
            self._insights.notify_vtex_account_migration(
                project_uuid=str(project.uuid),
                vtex_account=project.vtex_account,
            )
            logger.info(f"Notified Insights migration for project={project.uuid}")
        except Exception as exc:
            logger.error(
                f"Failed to notify Insights migration for "
                f"project={project.uuid}: {exc}"
            )
