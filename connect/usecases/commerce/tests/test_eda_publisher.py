from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from weni.eda.django.connection_params import AMQConnectionParamsFactory

from connect.api.v1.tests.utils import create_user_and_token
from connect.common.mocks import StripeMockGateway
from connect.common.models import (
    BillingPlan,
    Organization,
    OrganizationRole,
    Project,
    TypeProject,
)
from connect.usecases.commerce.eda_publisher import CommerceEDAPublisher


@override_settings(USE_EDA_PERMISSIONS=False)
class CommerceEDAPublisherTestCase(TestCase):
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway):
        mock_get_gateway.return_value = StripeMockGateway()
        self.user, _ = create_user_and_token("commerce_eda_user")
        self.organization = Organization.objects.create(
            name="Commerce EDA Org",
            description="Commerce EDA Org",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        self.organization.authorizations.create(
            user=self.user, role=OrganizationRole.ADMIN.value
        )
        self.project = Project.objects.create(
            name="Commerce Project",
            organization=self.organization,
            created_by=self.user,
            vtex_account="test-store",
            project_type=TypeProject.COMMERCE,
            language="pt-br",
        )

    @override_settings(USE_EDA=True, TESTING=False)
    @patch("connect.usecases.commerce.eda_publisher.EDAPublisher")
    @patch("connect.usecases.commerce.eda_publisher.RabbitmqPublisher")
    def test_publish_project_created_publishes_to_rabbitmq_and_amazonmq(
        self, mock_rabbitmq, mock_eda_publisher
    ):
        mock_rabbitmq_instance = Mock()
        mock_rabbitmq.return_value = mock_rabbitmq_instance
        mock_amazonmq_instance = Mock()
        mock_eda_publisher.return_value = mock_amazonmq_instance

        publisher = CommerceEDAPublisher()
        publisher.publish_project_created(self.project)

        mock_rabbitmq_instance.send_message.assert_called_once_with(
            body=publisher._build_project_body(self.project),
            exchange="projects.topic",
            routing_key="",
        )
        mock_eda_publisher.assert_called_once_with(AMQConnectionParamsFactory)
        mock_amazonmq_instance.send_message.assert_called_once_with(
            publisher._build_project_body(self.project),
            exchange="projects.topic",
            routing_key="project.created",
        )

    @override_settings(USE_EDA=False, TESTING=False)
    @patch("connect.usecases.commerce.eda_publisher.EDAPublisher")
    @patch("connect.usecases.commerce.eda_publisher.RabbitmqPublisher")
    def test_publish_project_created_skips_when_eda_disabled(
        self, mock_rabbitmq, mock_eda_publisher
    ):
        publisher = CommerceEDAPublisher()

        publisher.publish_project_created(self.project)

        mock_rabbitmq.assert_not_called()
        mock_eda_publisher.assert_not_called()

    @override_settings(USE_EDA=True, TESTING=False)
    @patch("connect.usecases.commerce.eda_publisher.RabbitmqPublisher")
    def test_publish_org_created_does_not_publish_to_amazonmq(self, mock_rabbitmq):
        mock_rabbitmq_instance = Mock()
        mock_rabbitmq.return_value = mock_rabbitmq_instance

        publisher = CommerceEDAPublisher()
        publisher.publish_org_created(self.organization, self.user)

        mock_rabbitmq_instance.send_message.assert_called_once_with(
            body=publisher._build_org_body(self.organization, self.user),
            exchange="orgs.topic",
            routing_key="",
        )
