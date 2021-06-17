from django.core.management.base import BaseCommand

from weni.utils import get_grpc_types


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        print(
            get_grpc_types()
            .get("inteligence")
            .list_organizations(user_email="daniel.yohan@ilhasoft.com.br")
        )
        # print(
        #     get_grpc_types()
        #     .get("inteligence")
        #     .get_user_organization_permission_role(
        #         user_email="daniel.yohan@ilhasoft.com.br", organization_id=779
        #     )
        # )
        # print(
        #     get_grpc_types()
        #     .get("inteligence")
        #     .create_organization(
        #         organization_name="Test Org",
        #         user_email="user@test.com",
        #     )
        # )
        # print(
        #     get_grpc_types()
        #         .get("inteligence")
        #         .create_organization(
        #         organization_name="xxxx",
        #         user_email="suporte@ilhasoft.com.br",
        #     )
        # )
        # print(
        #     get_grpc_types()
        #     .get("inteligence")
        #     .update_organization(
        #         organization_id=7,
        #         organization_name="testee23",
        #     )
        # )

        # print(
        #     get_grpc_types()
        #     .get("flow")
        #     .create_project(
        #         project_name="teste project",
        #         user_email="daniel.yohan@ilhasoft.com.br",
        #         project_timezone="America/Sao_Paulo",
        #     )
        # )

        # print(
        #     get_grpc_types()
        #     .get("flow")
        #     .get_classifiers(
        #         organization_uuid="b0c8641b-7382-467d-8b64-25e6229fea7d",
        #         classifier_type="bothub",
        #         is_active = True
        #     )
        # )

        # print(
        #     get_grpc_types()
        #     .get("flow")
        #     .update_language(
        #         user_email="daniel.yohan@ilhasoft.com.br",
        #         language="en-us",
        #     )
        # )

        # print(
        #     get_grpc_types()
        #     .get("flow")
        #     .get_project_flows(
        #         project_uuid="9a18c7a9-ab46-413d-88d4-90c04a5bb84e",
        #         flow_name="te",
        #     )
        # )
