from django.conf import settings

import requests

from connect.api.v1.internal.internal_authentication import InternalAuthentication
from connect.common.models import ProjectAuthorization, ProjectRole


class ChatsRESTClient:
    def __init__(self):
        from connect.common.models import ChatsRole

        self.base_url = settings.CHATS_REST_ENDPOINT
        self.authentication_instance = InternalAuthentication()
        self.permission_mapper = {
            ChatsRole.ADMIN.value: 1,
            ChatsRole.AGENT.value: 2,
            ChatsRole.SERVICE_MANAGER.value: 3,
        }

    def update_user_permission(
        self, permission: int, user_email: str, project_uuid: str
    ):
        user_auth = ProjectAuthorization.objects.get(
            user__email=user_email, project=project_uuid
        )
        user_role = user_auth.role
        chats_role = None
        dict_admin_role = {
            ProjectRole.CONTRIBUTOR.value: 2,
            ProjectRole.MODERATOR.value: 3,
        }
        dict_attendent_role = {
            ProjectRole.VIEWER.value: 1,
            ProjectRole.CHAT_USER.value: 2,
        }
        if user_role in dict_admin_role:
            chats_role = 1
        elif user_role in dict_attendent_role:
            chats_role = 2
        else:
            raise Exception("User role not found")

        body = dict(role=chats_role, user=user_email, project=project_uuid)
        requests.put(
            url=f"{self.base_url}/v1/internal/permission/project/",
            headers=self.authentication_instance.headers,
            json=body,
        )
        return True

    def update_user_language(self, user_email: str, language: str):
        body = dict(language=language)
        requests.put(
            url=f"{self.base_url}/v1/internal/user/language/?email={user_email}",
            headers=self.authentication_instance.headers,
            json=body,
        )
        return True

    def update_user(
        self,
        user_email: str,
        first_name: str = None,
        last_name: str = None,
        photo_url: str = None,
    ):
        body = dict(email=user_email)

        if first_name:
            body.update(dict(first_name=first_name))

        if last_name:
            body.update(dict(last_name=last_name))

        if photo_url:
            body.update(dict(photo_url=photo_url))

        requests.post(
            url=f"{self.base_url}/v1/internal/user/",
            headers=self.authentication_instance.headers,
            json=body,
        )

    def create_chat_project(
        self,
        project_uuid: str,
        project_name: str,
        date_format: str,
        timezone: str,
        is_template: bool,
        user_email: str,
    ):
        body = dict(
            uuid=project_uuid,
            name=project_name,
            date_format=date_format,
            timezone=timezone,
            is_template=is_template,
            user_email=user_email,
        )
        response = requests.post(
            url=f"{self.base_url}/v1/internal/project/",
            headers=self.authentication_instance.headers,
            json=body,
        )
        return response

    def delete_chat(self, project_uuid: str):
        requests.delete(
            url=f"{self.base_url}/v1/internal/project/{project_uuid}/",
            headers=self.authentication_instance.headers,
        )

    def create_user_permission(
        self, project_uuid: str, user_email: str, permission: int
    ):
        from connect.common.models import ChatsRole

        permission_mapper = {
            ChatsRole.ADMIN.value: 1,
            ChatsRole.AGENT.value: 2,
            ChatsRole.SERVICE_MANAGER.value: 3,
        }

        body = dict(
            role=permission_mapper.get(permission, 0),
            user=user_email,
            project=str(project_uuid),
        )
        requests.post(
            url=f"{self.base_url}/v1/internal/permission/project/",
            headers=self.authentication_instance.headers,
            json=body,
        )
        return True

    def update_chats_project(self, project_uuid):
        from connect.common.models import Project

        project = Project.objects.get(uuid=project_uuid)
        body = dict(
            project=str(project.uuid),
            name=project.name,
            timezone=str(project.timezone),
            date_format=project.date_format,
        )
        requests.patch(
            url=f"{self.base_url}/v1/internal/project/{project_uuid}/",
            headers=self.authentication_instance.headers,
            json=body,
        )
        return True

    def delete_user_permission_project(
        self, project_uuid: str, user_email: str, permission: int
    ):
        body = dict(
            user=user_email,
            project=str(project_uuid),
            role=self.permission_mapper.get(permission, 0),
        )
        requests.delete(
            url=f"{self.base_url}/v1/internal/permission/project/",
            headers=self.authentication_instance.headers,
            json=body,
        )
        return True
