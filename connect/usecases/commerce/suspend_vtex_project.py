import logging

from connect.common.models import BillingPlan, Project
from connect.usecases.commerce.dto import SuspendVtexProjectDTO

logger = logging.getLogger(__name__)


class SuspendVtexProjectUseCase:
    """Suspends a VTEX commerce project's trial due to reaching the conversation limit.

    Reuses the same suspension flow as trial time expiration (end_trial_period),
    but sends a specific email informing the conversation limit was reached.
    """

    def execute(self, dto: SuspendVtexProjectDTO) -> dict:
        project = Project.objects.get(uuid=dto.project_uuid)
        organization = project.organization
        billing = organization.organization_billing

        if organization.is_suspended:
            logger.info(
                f"Project {dto.project_uuid} already suspended, skipping"
            )
            return {
                "project_uuid": str(project.uuid),
                "already_suspended": True,
            }

        if billing.plan != BillingPlan.PLAN_TRIAL:
            raise ValueError(
                f"Project {dto.project_uuid} is not on a trial plan. "
                f"Current plan: {billing.plan}"
            )

        logger.info(
            f"Suspending project {dto.project_uuid} "
            f"due to conversation limit ({dto.conversation_limit})"
        )

        billing.end_trial_period()
        billing.send_email_trial_plan_expired_due_conversation_limit(
            dto.conversation_limit
        )

        return {"project_uuid": str(project.uuid), "suspended": True}
