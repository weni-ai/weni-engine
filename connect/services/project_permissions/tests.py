import uuid
from http import HTTPStatus
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings

from connect.api.v1.tests.utils import create_user_and_token
from connect.common.mocks import StripeMockGateway
from connect.common.models import (
    BillingPlan,
    Organization,
    OrganizationRole,
    Project,
    ProjectAuthorization,
    ProjectRole,
)
from connect.services.project_permissions.service import ProjectUserPermissionsService
from connect.usecases.authorizations.exceptions import (
    ProjectAuthorizationNotFoundError,
    UserNotFoundError,
)
from connect.usecases.authorizations.get_project_authorization import (
    GetProjectAuthorizationUseCase,
)


@override_settings(USE_EDA_PERMISSIONS=False)
class ProjectUserPermissionsServiceTestCase(TestCase):
    @patch("connect.authentication.signals.RabbitmqPublisher")
    @patch("connect.common.signals.RabbitmqPublisher")
    @patch("connect.common.signals.update_user_permission_project")
    @patch("connect.billing.get_gateway")
    def setUp(
        self,
        mock_get_gateway,
        mock_permission,
        mock_rabbitmq_common,
        mock_rabbitmq_auth,
    ):
        mock_get_gateway.return_value = StripeMockGateway()
        mock_permission.return_value = True
        mock_rabbitmq_common.return_value = Mock()
        mock_rabbitmq_auth.return_value = Mock()

        self.user, _ = create_user_and_token("perm-user")
        self.organization = Organization.objects.create(
            name="perm-org",
            description="perm-org",
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        self.org_authorization = self.organization.authorizations.create(
            user=self.user,
            role=OrganizationRole.ADMIN.value,
        )
        self.project = Project.objects.create(
            name="perm-project",
            organization=self.organization,
            flow_organization=uuid.uuid4(),
        )
        ProjectAuthorization.objects.filter(user=self.user).delete()

    def _create_authorization(self, role: ProjectRole) -> ProjectAuthorization:
        return ProjectAuthorization.objects.create(
            user=self.user,
            project=self.project,
            role=role.value,
            organization_authorization=self.org_authorization,
        )

    def test_returns_role_for_each_project_role(self):
        service = ProjectUserPermissionsService()

        for role in ProjectRole:
            with self.subTest(role=role.name):
                ProjectAuthorization.objects.filter(user=self.user).delete()
                self._create_authorization(role)

                status_code, body = service.get_user_permissions(
                    project_uuid=str(self.project.uuid),
                    user_email=self.user.email,
                )

                self.assertEqual(status_code, HTTPStatus.OK)
                self.assertEqual(body, {"project_authorization": role.value})

    def test_returns_404_when_authorization_missing(self):
        service = ProjectUserPermissionsService()

        status_code, body = service.get_user_permissions(
            project_uuid=str(self.project.uuid),
            user_email=self.user.email,
        )

        self.assertEqual(status_code, HTTPStatus.NOT_FOUND)
        self.assertEqual(body, {})

    def test_returns_404_when_user_does_not_exist(self):
        service = ProjectUserPermissionsService()

        status_code, body = service.get_user_permissions(
            project_uuid=str(self.project.uuid),
            user_email="missing@weni.ai",
        )

        self.assertEqual(status_code, HTTPStatus.NOT_FOUND)
        self.assertEqual(body, {})

    def test_delegates_to_injected_usecase(self):
        authorization = Mock(role=ProjectRole.CONTRIBUTOR.value)
        usecase = Mock(spec=GetProjectAuthorizationUseCase)
        usecase.get_by_project_uuid.return_value = authorization
        service = ProjectUserPermissionsService(get_authorization_usecase=usecase)

        status_code, body = service.get_user_permissions(
            project_uuid=str(self.project.uuid),
            user_email=self.user.email,
            user_token="ignored-token",
        )

        self.assertEqual(status_code, HTTPStatus.OK)
        self.assertEqual(body, {"project_authorization": ProjectRole.CONTRIBUTOR.value})
        usecase.get_by_project_uuid.assert_called_once_with(
            user_email=self.user.email,
            project_uuid=str(self.project.uuid),
        )

    def test_maps_usecase_not_found_errors_to_404(self):
        usecase = Mock(spec=GetProjectAuthorizationUseCase)
        usecase.get_by_project_uuid.side_effect = UserNotFoundError()
        service = ProjectUserPermissionsService(get_authorization_usecase=usecase)

        status_code, body = service.get_user_permissions(
            project_uuid=str(self.project.uuid),
            user_email=self.user.email,
        )

        self.assertEqual(status_code, HTTPStatus.NOT_FOUND)
        self.assertEqual(body, {})

        usecase.get_by_project_uuid.side_effect = ProjectAuthorizationNotFoundError()
        status_code, body = service.get_user_permissions(
            project_uuid=str(self.project.uuid),
            user_email=self.user.email,
        )

        self.assertEqual(status_code, HTTPStatus.NOT_FOUND)
        self.assertEqual(body, {})
