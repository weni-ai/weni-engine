import uuid
from unittest.mock import MagicMock, patch

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
from connect.usecases.auth.generate_session_token import (
    GenerateSessionTokenUseCase,
    ProjectAuthorizationNotFound,
)


@override_settings(USE_EDA_PERMISSIONS=False)
class GenerateSessionTokenUseCaseTestCase(TestCase):
    @patch(
        "connect.internals.event_driven.producer.rabbitmq_publisher.RabbitmqPublisher.send_message"
    )
    @patch("connect.common.signals.update_user_permission_project")
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway, mock_permission, mock_publisher):
        mock_get_gateway.return_value = StripeMockGateway()
        mock_permission.return_value = True

        self.user, _ = create_user_and_token("user")
        self.organization = Organization.objects.create(
            name="test organization",
            description="",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="free",
        )
        self.org_auth = self.organization.authorizations.create(
            user=self.user, role=OrganizationRole.ADMIN.value
        )
        self.project = Project.objects.create(
            name="test project",
            flow_organization=uuid.uuid4(),
            organization=self.organization,
        )
        ProjectAuthorization.objects.filter(user=self.user).delete()
        ProjectAuthorization.objects.create(
            project=self.project,
            user=self.user,
            role=ProjectRole.MODERATOR.value,
            organization_authorization=self.org_auth,
        )

    @patch(
        "connect.usecases.auth.generate_session_token.DynamoDBSessionTokenRepository"
    )
    @patch("connect.usecases.auth.generate_session_token.get_redis_connection")
    def test_execute_generates_token_for_authorized_user(
        self, mock_get_redis_connection, mock_repo_cls
    ):
        mock_redis = MagicMock()
        mock_get_redis_connection.return_value = mock_redis
        mock_repo = MagicMock()
        mock_repo_cls.return_value = mock_repo

        token_hash = GenerateSessionTokenUseCase().execute(
            project_uuid=str(self.project.uuid),
            user=self.user,
            duration=3600,
        )

        self.assertTrue(token_hash)
        mock_repo.put.assert_called_once()
        put_kwargs = mock_repo.put.call_args.kwargs
        self.assertEqual(put_kwargs["token_hash"], token_hash)
        self.assertEqual(put_kwargs["project"], str(self.project.uuid))
        self.assertEqual(put_kwargs["user"], self.user.email)
        mock_redis.setex.assert_called_once()

    def test_execute_raises_when_user_has_no_project_authorization(self):
        other_user, _ = create_user_and_token("other")

        with self.assertRaises(ProjectAuthorizationNotFound):
            GenerateSessionTokenUseCase().execute(
                project_uuid=str(self.project.uuid),
                user=other_user,
                duration=3600,
            )
