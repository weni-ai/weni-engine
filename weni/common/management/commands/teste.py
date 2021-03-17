from django.core.management.base import BaseCommand

from weni.utils import get_grpc_types


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        # print(get_grpc_types().get('inteligence').list_organizations(user_email='daniel.yohan@ilhasoft.com.br'))
        # print(
        #     get_grpc_types()
        #     .get("inteligence")
        #     .get_user_organization_permission_role(
        #         user_email="daniel.yohan@ilhasoft.com.br", organization_id=779
        #     )
        # )
        print(
            get_grpc_types()
            .get("inteligence")
            .create_organization(
                organization_name="Test Org",
                user_email="user@test.com",
                user_nickname="testuser",
            )
        )
