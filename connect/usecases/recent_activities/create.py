from connect.common.models import Project
from connect.authentication.models import User
from connect.common.models import RecentActivity


class RecentActivityUseCase:
    def create_recent_activity(
        self,
        user_email: str,
        project_uuid: str,
        action: str,
        entity: str,
        entity_name: str
    ) -> RecentActivity:

        user = User.objects.get(email=user_email)
        project = Project.objects.get(uuid=project_uuid)

        recet_activity = RecentActivity.objects.create(
            user=user,
            project=project,
            action=action,
            entity=entity,
            entity_name=entity_name
        )

        return recet_activity
