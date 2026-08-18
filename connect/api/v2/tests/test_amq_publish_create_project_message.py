from unittest.mock import MagicMock, Mock, patch

from django.test import TestCase, override_settings
from weni.eda.django.connection_params import AMQConnectionParamsFactory

from connect.api.v1.tests.utils import create_user_and_token
from connect.api.v2.commerce.serializers import CommerceSerializer
from connect.api.v2.projects.serializers import ProjectSerializer
from connect.common.mocks import StripeMockGateway
from connect.common.models import (
    BillingPlan,
    Organization,
    OrganizationRole,
    Project,
    TypeProject,
)


@override_settings(USE_EDA_PERMISSIONS=False, EDA_PRODUCER="connect-test-producer")
class PublishCreateProjectMessageTestCase(TestCase):
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway):
        mock_get_gateway.return_value = StripeMockGateway()
        self.user, _ = create_user_and_token("amq_publish_user")
        self.organization = Organization.objects.create(
            name="AMQ Publish Org",
            description="AMQ Publish Org",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        self.organization.authorizations.create(
            user=self.user, role=OrganizationRole.ADMIN.value
        )
        self.project = Project.objects.create(
            name="AMQ Publish Project",
            organization=self.organization,
            created_by=self.user,
            vtex_account="amq-store",
            project_type=TypeProject.COMMERCE,
            language="pt-br",
        )

    @patch("connect.api.v2.commerce.serializers.EDAPublisher")
    @patch("connect.api.v2.commerce.serializers.RabbitmqPublisher")
    def test_commerce_serializer_publishes_to_rabbitmq_and_amazonmq(
        self, mock_rabbitmq, mock_eda_publisher
    ):
        mock_rabbitmq_instance = Mock()
        mock_rabbitmq.return_value = mock_rabbitmq_instance
        mock_amazonmq_instance = Mock()
        mock_eda_publisher.return_value = mock_amazonmq_instance

        serializer = CommerceSerializer()
        serializer.publish_create_project_message(self.project, self.user)

        rabbitmq_body = mock_rabbitmq_instance.send_message.call_args.args[0]
        mock_rabbitmq_instance.send_message.assert_called_once_with(
            rabbitmq_body,
            exchange="projects.topic",
            routing_key="",
        )
        mock_eda_publisher.assert_called_once_with(AMQConnectionParamsFactory)
        amazonmq_body = mock_amazonmq_instance.send_message.call_args.args[0]
        mock_amazonmq_instance.send_message.assert_called_once_with(
            amazonmq_body,
            exchange="projects.topic",
            routing_key="project.created",
        )
        self.assertEqual(amazonmq_body["event_type"], "project.created")
        self.assertEqual(amazonmq_body["producer"], "connect-test-producer")
        self.assertEqual(amazonmq_body["data"], rabbitmq_body)
        self.assertIn("currency", rabbitmq_body)

    @patch("connect.api.v2.projects.serializers.EDAPublisher")
    @patch("connect.api.v2.projects.serializers.RabbitmqPublisher")
    def test_project_serializer_publishes_to_rabbitmq_and_amazonmq(
        self, mock_rabbitmq, mock_eda_publisher
    ):
        mock_rabbitmq_instance = Mock()
        mock_rabbitmq.return_value = mock_rabbitmq_instance
        mock_amazonmq_instance = Mock()
        mock_eda_publisher.return_value = mock_amazonmq_instance

        request = MagicMock()
        request.data = {}
        serializer = ProjectSerializer(context={"request": request})
        serializer.publish_create_project_message(self.project, brain_on=True)

        rabbitmq_body = mock_rabbitmq_instance.send_message.call_args.args[0]
        mock_rabbitmq_instance.send_message.assert_called_once_with(
            rabbitmq_body,
            exchange="projects.topic",
            routing_key="",
        )
        self.assertTrue(rabbitmq_body["brain_on"])
        mock_eda_publisher.assert_called_once_with(AMQConnectionParamsFactory)
        amazonmq_body = mock_amazonmq_instance.send_message.call_args.args[0]
        mock_amazonmq_instance.send_message.assert_called_once_with(
            amazonmq_body,
            exchange="projects.topic",
            routing_key="project.created",
        )
        self.assertEqual(amazonmq_body["event_type"], "project.created")
        self.assertEqual(amazonmq_body["producer"], "connect-test-producer")
        self.assertEqual(amazonmq_body["data"], rabbitmq_body)
        self.assertIn("currency", rabbitmq_body)
