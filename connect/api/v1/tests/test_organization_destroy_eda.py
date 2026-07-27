import uuid as uuid_lib
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from connect.api.v1.organization.views import OrganizationViewSet
from connect.authentication.models import User
from connect.common.models import BillingPlan, Organization


@override_settings(
    USE_EDA_PERMISSIONS=False,
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "organization-destroy-eda-tests",
        }
    },
)
class OrganizationDestroyEDATestCase(TestCase):
    @patch("connect.authentication.signals.RabbitmqPublisher")
    @patch("connect.common.signals.RabbitmqPublisher")
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway, mock_common_rabbitmq, mock_auth_rabbitmq):
        from connect.common.mocks import StripeMockGateway

        mock_get_gateway.return_value = StripeMockGateway()

        self.user = User.objects.create_user("admin@user.com", "admin")
        self.organization = Organization.objects.create(
            name="Test Org",
            inteligence_organization=123,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="free",
        )
        self.project_one = self.organization.project.create(
            name="project one",
            timezone="America/Sao_Paulo",
            flow_organization=uuid_lib.uuid4(),
        )
        self.project_two = self.organization.project.create(
            name="project two",
            timezone="America/Sao_Paulo",
            flow_organization=uuid_lib.uuid4(),
        )

        self.view = OrganizationViewSet()
        self.view.request = MagicMock()
        self.view.request.user = self.user

    @patch("connect.api.v1.organization.views.IntelligenceRESTClient")
    @patch("connect.api.v1.organization.views.ProjectEDAPublisher")
    def test_perform_destroy_publishes_deleted_event_for_each_project(
        self, mock_eda_publisher, mock_ai_client
    ):
        mock_publisher = MagicMock()
        mock_eda_publisher.return_value = mock_publisher
        mock_ai_client.return_value.delete_organization.return_value = None

        organization_uuid = self.organization.uuid

        self.view.perform_destroy(self.organization)

        self.assertFalse(Organization.objects.filter(uuid=organization_uuid).exists())
        self.assertEqual(mock_publisher.publish_project_deleted.call_count, 2)

        published_uuids = {
            call.kwargs["project_uuid"]
            for call in mock_publisher.publish_project_deleted.call_args_list
        }
        self.assertEqual(
            published_uuids,
            {self.project_one.uuid, self.project_two.uuid},
        )
        for call in mock_publisher.publish_project_deleted.call_args_list:
            self.assertEqual(call.kwargs["user_email"], self.user.email)
