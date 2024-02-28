from connect.authentication.models import User
from connect.common.models import RecentActivity


class RecentActivityUseCase:
    def create_recent_activity(
        msg_body
    ) -> RecentActivity:

        user = User.objects.get(email=msg_body.get("user"))

        new_activity = RecentActivity.create_recent_activities(msg_body, user)

        return new_activity
