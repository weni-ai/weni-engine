from django.test import TestCase
import uuid
from connect.common.models import (
    Organization,
    BillingPlan,
    Project,
    User,
    OrganizationRole,
    RequestPermissionProject,
)
from connect.usecases.project_authorizations.create import ProjectAuthorizationUseCase

from connect.usecases.project.exceptions import ProjectDoesNotExist
from connect.usecases.organizations.exceptions import OrganizationDoesNotExist
from connect.usecases.users.exceptions import UserDoesNotExist


class ProjectAuthorizationUseCaseTestCase(TestCase):
    def setUp(self):
        self.usecase = ProjectAuthorizationUseCase()
        self.organization = Organization.objects.create(
            name="test organization",
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_ENTERPRISE,
        )
        self.project = Project.objects.create(
            name="Project",
            organization=self.organization,
        )
        self.user = User.objects.create(
            email="user@does.exists",
            username="user@does.exists"
        )
        self.crm = User.objects.create(
            email="crm@email.com",
            username="crm@email.com"
        )

        self.not_org = str(uuid.uuid4())
        self.not_project = str(uuid.uuid4())
        self.not_user = "userdoes@not.exist"

    def test_user_does_not_exist(self):
        msg_body = {
            "user": self.not_user,
            "org_uuid": self.not_org,
            "project_uuid": self.not_project,
        }
        with self.assertRaises(UserDoesNotExist):
            self.usecase.create_project_authorization(msg_body)

    def test_org_does_not_exist(self):
        msg_body = {
            "user": self.user.email,
            "org_uuid": self.not_org,
            "project_uuid": self.not_project,
        }
        with self.assertRaises(OrganizationDoesNotExist):
            self.usecase.create_project_authorization(msg_body)

    def test_project_does_not_exist(self):
        msg_body = {
            "user": self.user.email,
            "org_uuid": str(self.organization.uuid),
            "project_uuid": self.not_project,
        }
        with self.assertRaises(ProjectDoesNotExist):
            self.usecase.create_project_authorization(msg_body)

    def test_org_auth_does_not_exist(self):
        """This tests project authorization creation if a user was invited to a single project and not the org"""
        msg_body = {
            "user": self.user.email,
            "org_uuid": str(self.organization.uuid),
            "project_uuid": str(self.project.uuid),
            "role": 3,
        }
        project_auth = self.usecase.create_project_authorization(msg_body)
        self.assertEquals(
            project_auth.organization_authorization.role,
            OrganizationRole.VIEWER.value
        )
        self.assertEquals(
            project_auth.role, msg_body.get("role")
        )
    
    def test_org_auth_exists(self):
        self.organization.authorizations.create(user=self.user, role=3)
        msg_body = {
            "user": self.user.email,
            "org_uuid": str(self.organization.uuid),
            "project_uuid": str(self.project.uuid),
            "role": 3,
        }
        project_auth = self.usecase.create_project_authorization(msg_body)
        self.assertEquals(
            project_auth.organization_authorization.role,
            OrganizationRole.ADMIN.value
        )
        self.assertEquals(
            project_auth.role, msg_body.get("role")
        )

    def test_create_request_permission_project(self):
        RequestPermissionProject.objects.create(
            email=self.user,
            project=self.project,
            role=3,
            created_by=self.crm,
        )