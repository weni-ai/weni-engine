import json
from typing import Dict
from unittest import skipIf
import unittest

from django.test import TestCase, RequestFactory

from connect.common.models import (
    BillingPlan,
    Organization,
    User,
    RequestPermissionOrganization,
    RequestPermissionProject,
    OrganizationAuthorization,
    ProjectAuthorization,
)

from connect.usecases.authorizations.create import CreateAuthorizationUseCase
from connect.usecases.authorizations.update import UpdateAuthorizationUseCase
from connect.usecases.authorizations.delete import DeleteAuthorizationUseCase

from connect.usecases.authorizations.dto import (
    CreateAuthorizationDTO,
    UpdateAuthorizationDTO,
    DeleteAuthorizationDTO,
    CreateProjectAuthorizationDTO,
)

from connect.api.v2.organizations.views import OrganizationViewSet
from connect.api.v1.project.views import RequestPermissionProjectViewSet, ProjectViewSet
from connect.api.v1.tests.utils import create_user_and_token


class MockRabbitMQPublisher:
    def send_message(self, body: Dict, exchange: str, routing_key: str):
        msg = f"Sending {body} to {exchange}"
        if routing_key:
            msg += f":{routing_key}"
        print(msg)
        return


class TestCaseSetUp:
    def create_auth(self, user: User, org: Organization, role: int, publish_message: bool = False):

        auth_dto = CreateAuthorizationDTO(
            user_email=user.email,
            org_uuid=str(org.uuid),
            role=role,
        )
        usecase = CreateAuthorizationUseCase(MockRabbitMQPublisher(), publish_message)
        return usecase.create_authorization(auth_dto)


@unittest.skip("Test broken, need to be fixed")
class AuthorizationsTestCase(TestCase, TestCaseSetUp):

    def setUp(self):
        self.superuser = self.user = User.objects.create(
            email="super@test.user",
            username="superuser"
        )
        self.user = User.objects.create(
            email="eda@test.user",
            username="EdaTestUser",
            has_2fa=True
        )
        self.org = Organization.objects.create(
            name="Eda test org",
            description="Eda test org",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        self.project = self.org.project.create(name="Eda test project")

    @skipIf(True, "Tests signal and rabbitmq connection")
    def test_signal_create_permission_if_user_exists(self):
        """Test create request permission signal"""
        role = 3
        request_permission = RequestPermissionOrganization.objects.create(
            organization=self.org,
            role=role,
            email=self.user.email,
            created_by=self.superuser
        )

        with self.assertRaises(RequestPermissionOrganization.DoesNotExist):
            RequestPermissionOrganization.objects.get(id=request_permission.id)

        authorization: OrganizationAuthorization = self.org.get_user_authorization(self.user)
        project_authorization: ProjectAuthorization = self.project.get_user_authorization(self.user)

        self.assertEquals(role, authorization.role)
        self.assertEquals(role, project_authorization.role)
        self.assertEquals(self.user.has_2fa, authorization.has_2fa)

    def test_create_permission(self):
        role = 3

        self.create_auth(self.user, self.org, role)
        authorization = self.org.authorizations.get(user=self.user)

        self.assertEqual(authorization.role, role)

    def test_update_permission(self):
        role = 3

        self.create_auth(self.user, self.org, role)

        update_role = 2
        auth_dto = UpdateAuthorizationDTO(
            user_email=self.user.email,
            org_uuid=str(self.org.uuid),
            role=update_role,
            request_user=self.superuser.email
        )

        project_authorization: ProjectAuthorization = self.project.get_user_authorization(self.user)
        
        usecase = UpdateAuthorizationUseCase(message_publisher=MockRabbitMQPublisher())
        authorization = usecase.update_authorization(auth_dto)

        project_authorization.refresh_from_db()

        self.assertEquals(authorization.role, update_role)
        self.assertEquals(project_authorization.role, update_role)

    def test_delete_permission(self):
        role = 3
        self.create_auth(self.user, self.org, role)

        auth_dto = DeleteAuthorizationDTO(
            user_email=self.user.email,
            org_uuid=str(self.org.uuid),
            request_user=self.superuser.email
        )

        usecase = DeleteAuthorizationUseCase(message_publisher=MockRabbitMQPublisher())
        usecase.delete_authorization(auth_dto)

        self.assertEqual(self.org.authorizations.count(), 0)
        self.assertEqual(self.project.project_authorizations.count(), 0)


    def test_create_authorization_for_a_single_project(self):
        role = 3

        auth_dto = CreateProjectAuthorizationDTO(
            user_email=self.user.email,
            project_uuid=str(self.project.uuid),
            role=role,
            created_by_email=self.superuser.email
        )
        usecase = CreateAuthorizationUseCase(MockRabbitMQPublisher())
        project_auth: ProjectAuthorization = usecase.create_authorization_for_a_single_project(auth_dto)
        org_auth = self.org.authorizations.get(user=self.user)

        self.assertEquals(project_auth.role, role)
        self.assertEquals(org_auth.role, 1)

    def test_create_authorization_for_a_single_project_if_org_auth_exists(self):
        org_auth = self.org.authorizations.create(user=self.user, role=1)

        role = 2

        auth_dto = CreateProjectAuthorizationDTO(
            user_email=self.user.email,
            project_uuid=str(self.project.uuid),
            role=role,
            created_by_email=self.superuser.email
        )
        usecase = CreateAuthorizationUseCase(MockRabbitMQPublisher())
        project_auth: ProjectAuthorization = usecase.create_authorization_for_a_single_project(auth_dto)
        org_auth = self.org.authorizations.get(user=self.user)

        self.assertEquals(project_auth.role, role)
        self.assertEquals(org_auth.role, 1)
    
    def test_create_project_auth_if_user_dosent_exist(self):
        role = 2
        user_email = "user@dosent.exist"
        auth_dto = CreateProjectAuthorizationDTO(
            user_email=user_email,
            project_uuid=str(self.project.uuid),
            role=role,
            created_by_email=self.superuser.email
        )
        usecase = CreateAuthorizationUseCase(MockRabbitMQPublisher())
        project_auth: RequestPermissionProject = usecase.create_authorization_for_a_single_project(auth_dto)

        self.assertEqual(project_auth.email, user_email)


@skipIf(True, "Tests views and rabbitmq connection")
class EDAProjectAuthorizationsViewsTestCase(TestCase, TestCaseSetUp):
    def setUp(self):
        self.factory = RequestFactory()
        self.org = Organization.objects.create(
            name="Org",
            description="Org",
            organization_billing__plan="enterprise",
            organization_billing__cycle="monthly",
        )
        self.project = self.org.project.create(name="Project")

        self.owner, self.owner_token = create_user_and_token("owner")
        self.owner_auth = self.org.authorizations.create(user=self.owner, role=3)
        self.authorization_header = (
            {
                "HTTP_AUTHORIZATION": "Token {}".format(self.owner_token.key),
                "Content-Type": "application/json"
            }
        )

    def request_permission_project(self, data):
        request = self.factory.post(
            "/v1/project/request-permission/", data, **self.authorization_header
        )
        response = RequestPermissionProjectViewSet.as_view({"post": "create"})(request)
        response.render()
        content_data = json.loads(response.content)
        return content_data

    def request_project_viewset(self, project_uuid: str, data: Dict, method: Dict):
        request = self.factory.delete(
            f"/v1/organization/project/grpc/destroy-user-permission/{project_uuid}",
            data,
            content_type="application/json",
            **self.authorization_header
        )
        response = ProjectViewSet.as_view(method)(request, project_uuid=project_uuid)
        return response

    def test_request_permission_project_user_dosent_exists(self):
        role = 1
        data = {
            "email": "user@email.com",
            "project": str(self.project.uuid),
            "role": role,
        }
        
        content_data = self.request_permission_project(data)

        self.assertTrue(content_data["data"].get("is_pendent"))
        self.assertEquals(int(content_data["data"].get("role")), role)

    def test_request_permission_project_user_exists(self):
        role = 3
        user, _ = create_user_and_token("user")

        data = {
            "email": user.email,
            "project": str(self.project.uuid),
            "role": role,
        }

        content_data = self.request_permission_project(data)

        org_auth = self.org.authorizations.get(user=user)

        self.assertFalse(content_data["data"].get("is_pendent"))
        self.assertEquals(int(content_data["data"].get("role")), role)
        self.assertEquals(org_auth.role, 1)
    
    def test_request_permission_project_org_auth_exists(self):
        role = 3
        user, _ = create_user_and_token("user")

        org_auth: OrganizationAuthorization = self.org.authorizations.create(user=user, role=2)
        org_auth_role = org_auth.role

        data = {
            "email": user.email,
            "project": str(self.project.uuid),
            "role": role,
        }

        content_data = self.request_permission_project(data)

        org_auth.refresh_from_db()

        self.assertFalse(content_data["data"].get("is_pendent"))
        self.assertEquals(int(content_data["data"].get("role")), role)
        self.assertEquals(org_auth_role, org_auth.role)

    def test_request_permission_project_if_obj_exists(self):
        user_email = "user@email.com"

        RequestPermissionProject.objects.create(
            email=user_email,
            project=self.project,
            role=2,
            created_by=self.owner,
        )

        role = 1

        data = {
            "email": "user@email.com",
            "project": str(self.project.uuid),
            "role": role,
        }
        
        content_data = self.request_permission_project(data)

        self.assertTrue(content_data["data"].get("is_pendent"))
        self.assertEquals(int(content_data["data"].get("role")), role)

    def test_request_permission_project_if_project_auth_exists(self):
        user, _ = create_user_and_token("user")
        self.create_auth(user, self.org, 2)
        project_auth: ProjectAuthorization = self.project.project_authorizations.get(user=user)

        role = 3

        self.assertEqual(project_auth.role, 2)

        data = {
            "email": user.email,
            "project": str(self.project.uuid),
            "role": role,
        }

        content_data = self.request_permission_project(data)
        self.assertFalse(content_data["data"].get("is_pendent"))
        self.assertEquals(int(content_data["data"].get("role")), role)


    def test_delete_request_permission(self):
        email="user@not.exist"
        request_permission = RequestPermissionProject.objects.create(
            email=email,
            project=self.project,
            created_by=self.owner,
            role=3
        )
        data = {"email": email}
        self.request_project_viewset(
            data=data,
            project_uuid=str(self.project.uuid),
            method={"delete": "destroy_user_permission"}
        )
        with self.assertRaises(RequestPermissionOrganization.DoesNotExist):
            RequestPermissionOrganization.objects.get(id=request_permission.id)

    def test_delete_project_authorization(self):
        user, _ = create_user_and_token("user")
        self.create_auth(user, self.org, 2)
        project_auth: ProjectAuthorization = self.project.project_authorizations.get(user=user)
        data = {"email": user.email}
        response = self.request_project_viewset(
            data=data,
            project_uuid=str(self.project.uuid),
            method={"delete": "destroy_user_permission"}
        )
        self.assertEquals(response.status_code, 204)
        with self.assertRaises(ProjectAuthorization.DoesNotExist):
            ProjectAuthorization.objects.get(uuid=project_auth.uuid)


# @skipIf(True, "Tests views and rabbitmq connection")
class OrganizationViewSetTestCase(TestCase, TestCaseSetUp):
    def setUp(self):
        self.factory = RequestFactory()
        self.org = Organization.objects.create(
            name="Org",
            description="Org",
            organization_billing__plan="enterprise",
            organization_billing__cycle="monthly",
        )
        self.project = self.org.project.create(name="Project")

        self.owner, self.owner_token = create_user_and_token("owner")
        self.owner_auth = self.org.authorizations.create(user=self.owner, role=3)
        self.authorization_header = (
            {
                "HTTP_AUTHORIZATION": "Token {}".format(self.owner_token.key),
                "Content-Type": "application/json"
            }
        )

    def request_permission_project(self, data):
            request = self.factory.post(
                "/v2/organizations/",
                json.dumps(data),
                content_type="application/json",
                **self.authorization_header
            )
            response = OrganizationViewSet.as_view({"post": "create"})(request)
            response.render()
            content_data = json.loads(response.content)
            return content_data

    @unittest.skip("Test broken, need to be fixed")
    def test_create_org(self):
        user, _ = create_user_and_token("user")
        data = {
            "organization": {
                "name": "1",
                "description": "1",
                "organization_billing_plan": "trial",
                "customer": "",
                "authorizations": [{"user_email": user.email, "role": "3"}]
            },
            "project": {
                "date_format": "D",
                "name": "1",
                "description": "1",
                "timezone": "America/Sao_Paulo",
                "template": False,
                "uuid": "blank",
                "globals": {}
            }
        }

        content_data = self.request_permission_project(data)
        self.assertEquals(ProjectAuthorization.objects.count(), 2)
