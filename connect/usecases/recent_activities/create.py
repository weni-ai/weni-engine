from connect.authentication.models import User
from connect.common.models import RecentActivity
from connect.usecases.recent_activities.exceptions import InvalidActionEntityCombination


class RecentActivityUseCase:
    def create_recent_activity(self, msg_body) -> RecentActivity:
        user = User.objects.get(email=msg_body.get("user"))

        action = msg_body.get("action")
        entity = msg_body.get("entity")

        if not self._is_valid_action_entity_combination(action, entity):
            raise InvalidActionEntityCombination(
                f"Invalid combination of action '{action}' and entity '{entity}'"
            )

        new_activity = RecentActivity.create_recent_activities(msg_body, user)
        return new_activity

    def _is_valid_action_entity_combination(self, action, entity):
        return entity in RecentActivity.ACTIONS.get(action, [])
