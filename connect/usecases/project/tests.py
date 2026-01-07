import uuid
from unittest.mock import patch, Mock
from django.test import TestCase, override_settings
import pendulum

from connect.usecases.project.eda_publisher import ProjectEDAPublisher


class ProjectEDAPublisherTestCase(TestCase):
    def setUp(self):
        self.project_uuid = uuid.uuid4()
        self.user_email = "test@example.com"

    @override_settings(USE_EDA=True, TESTING=False)
    @patch("connect.usecases.project.eda_publisher.RabbitmqPublisher")
    def test_publisher_initialization_with_eda_enabled(self, mock_rabbitmq):
        """Test that RabbitmqPublisher is initialized when USE_EDA is True and TESTING is False"""
        publisher = ProjectEDAPublisher()

        mock_rabbitmq.assert_called_once()
        self.assertIsNotNone(publisher.rabbitmq_publisher)

    @override_settings(USE_EDA=False, TESTING=False)
    def test_publisher_initialization_with_eda_disabled(self):
        """Test that RabbitmqPublisher is not initialized when USE_EDA is False"""
        publisher = ProjectEDAPublisher()

        self.assertIsNone(publisher.rabbitmq_publisher)

    @override_settings(USE_EDA=True, TESTING=True)
    def test_publisher_initialization_with_testing_enabled(self):
        """Test that RabbitmqPublisher is not initialized when TESTING is True"""
        publisher = ProjectEDAPublisher()

        self.assertIsNone(publisher.rabbitmq_publisher)

    @override_settings(USE_EDA=True, TESTING=False)
    @patch("connect.usecases.project.eda_publisher.RabbitmqPublisher")
    def test_publish_project_deleted_with_default_timestamp(self, mock_rabbitmq):
        """Test publishing project deleted event with default timestamp"""
        mock_publisher_instance = Mock()
        mock_rabbitmq.return_value = mock_publisher_instance

        publisher = ProjectEDAPublisher()

        with patch("connect.usecases.project.eda_publisher.pendulum.now") as mock_now:
            mock_timestamp = pendulum.parse("2024-01-15T10:30:00Z")
            mock_now.return_value = mock_timestamp

            publisher.publish_project_deleted(
                project_uuid=self.project_uuid,
                user_email=self.user_email,
            )

        expected_body = {
            "project_uuid": str(self.project_uuid),
            "action": "deleted",
            "user_email": self.user_email,
            "timestamp": mock_timestamp.to_iso8601_string(),
        }

        mock_publisher_instance.send_message.assert_called_once_with(
            body=expected_body,
            exchange="update-projects.topic",
            routing_key="",
        )

    @override_settings(USE_EDA=True, TESTING=False)
    @patch("connect.usecases.project.eda_publisher.RabbitmqPublisher")
    def test_publish_project_deleted_with_custom_timestamp(self, mock_rabbitmq):
        """Test publishing project deleted event with custom timestamp"""
        mock_publisher_instance = Mock()
        mock_rabbitmq.return_value = mock_publisher_instance

        publisher = ProjectEDAPublisher()

        custom_timestamp = pendulum.parse("2024-01-15T15:45:30Z")

        publisher.publish_project_deleted(
            project_uuid=self.project_uuid,
            user_email=self.user_email,
            deleted_at=custom_timestamp,
        )

        expected_body = {
            "project_uuid": str(self.project_uuid),
            "action": "deleted",
            "user_email": self.user_email,
            "timestamp": custom_timestamp.to_iso8601_string(),
        }

        mock_publisher_instance.send_message.assert_called_once_with(
            body=expected_body,
            exchange="update-projects.topic",
            routing_key="",
        )

    @override_settings(USE_EDA=False, TESTING=False)
    def test_publish_project_deleted_without_rabbitmq(self):
        """Test that publish_project_deleted does nothing when rabbitmq_publisher is None"""
        publisher = ProjectEDAPublisher()

        # Should not raise any exception
        publisher.publish_project_deleted(
            project_uuid=self.project_uuid,
            user_email=self.user_email,
        )

    @override_settings(USE_EDA=True, TESTING=False)
    @patch("connect.usecases.project.eda_publisher.RabbitmqPublisher")
    def test_publish_project_updated_with_all_fields(self, mock_rabbitmq):
        """Test publishing project updated event with all optional fields"""
        mock_publisher_instance = Mock()
        mock_rabbitmq.return_value = mock_publisher_instance

        publisher = ProjectEDAPublisher()

        custom_timestamp = pendulum.parse("2024-01-15T12:00:00Z")

        publisher.publish_project_updated(
            project_uuid=self.project_uuid,
            user_email=self.user_email,
            name="Updated Project",
            description="Updated description",
            language="pt-br",
            timezone="America/Sao_Paulo",
            date_format="DD/MM/YYYY",
            updated_at=custom_timestamp,
        )

        expected_body = {
            "project_uuid": str(self.project_uuid),
            "action": "updated",
            "user_email": self.user_email,
            "name": "Updated Project",
            "description": "Updated description",
            "language": "pt-br",
            "timezone": "America/Sao_Paulo",
            "date_format": "DD/MM/YYYY",
            "timestamp": custom_timestamp.to_iso8601_string(),
        }

        mock_publisher_instance.send_message.assert_called_once_with(
            body=expected_body,
            exchange="update-projects.topic",
            routing_key="",
        )

    @override_settings(USE_EDA=True, TESTING=False)
    @patch("connect.usecases.project.eda_publisher.RabbitmqPublisher")
    def test_publish_project_updated_with_minimal_fields(self, mock_rabbitmq):
        """Test publishing project updated event with only required fields"""
        mock_publisher_instance = Mock()
        mock_rabbitmq.return_value = mock_publisher_instance

        publisher = ProjectEDAPublisher()

        with patch("connect.usecases.project.eda_publisher.pendulum.now") as mock_now:
            mock_timestamp = pendulum.parse("2024-01-15T10:30:00Z")
            mock_now.return_value = mock_timestamp

            publisher.publish_project_updated(
                project_uuid=self.project_uuid,
                user_email=self.user_email,
            )

        expected_body = {
            "project_uuid": str(self.project_uuid),
            "action": "updated",
            "user_email": self.user_email,
            "name": None,
            "description": None,
            "language": None,
            "timezone": None,
            "date_format": None,
            "timestamp": mock_timestamp.to_iso8601_string(),
        }

        mock_publisher_instance.send_message.assert_called_once_with(
            body=expected_body,
            exchange="update-projects.topic",
            routing_key="",
        )

    @override_settings(USE_EDA=True, TESTING=False)
    @patch("connect.usecases.project.eda_publisher.RabbitmqPublisher")
    def test_publish_project_updated_with_partial_fields(self, mock_rabbitmq):
        """Test publishing project updated event with some optional fields"""
        mock_publisher_instance = Mock()
        mock_rabbitmq.return_value = mock_publisher_instance

        publisher = ProjectEDAPublisher()

        custom_timestamp = pendulum.parse("2024-01-15T14:20:00Z")

        publisher.publish_project_updated(
            project_uuid=self.project_uuid,
            user_email=self.user_email,
            name="New Name",
            timezone="UTC",
            updated_at=custom_timestamp,
        )

        expected_body = {
            "project_uuid": str(self.project_uuid),
            "action": "updated",
            "user_email": self.user_email,
            "name": "New Name",
            "description": None,
            "language": None,
            "timezone": "UTC",
            "date_format": None,
            "timestamp": custom_timestamp.to_iso8601_string(),
        }

        mock_publisher_instance.send_message.assert_called_once_with(
            body=expected_body,
            exchange="update-projects.topic",
            routing_key="",
        )

    @override_settings(USE_EDA=False, TESTING=False)
    def test_publish_project_updated_without_rabbitmq(self):
        """Test that publish_project_updated does nothing when rabbitmq_publisher is None"""
        publisher = ProjectEDAPublisher()

        # Should not raise any exception
        publisher.publish_project_updated(
            project_uuid=self.project_uuid,
            user_email=self.user_email,
            name="Test Project",
        )

    @override_settings(USE_EDA=True, TESTING=False)
    @patch("connect.usecases.project.eda_publisher.RabbitmqPublisher")
    def test_publish_project_status_updated_with_default_timestamp(self, mock_rabbitmq):
        """Test publishing project status updated event with default timestamp"""
        mock_publisher_instance = Mock()
        mock_rabbitmq.return_value = mock_publisher_instance

        publisher = ProjectEDAPublisher()

        with patch("connect.usecases.project.eda_publisher.pendulum.now") as mock_now:
            mock_timestamp = pendulum.parse("2024-01-15T11:00:00Z")
            mock_now.return_value = mock_timestamp

            publisher.publish_project_status_updated(
                project_uuid=self.project_uuid,
                user_email=self.user_email,
                status="ACTIVE",
            )

        expected_body = {
            "project_uuid": str(self.project_uuid),
            "action": "status_updated",
            "user_email": self.user_email,
            "status": "ACTIVE",
            "timestamp": mock_timestamp.to_iso8601_string(),
        }

        mock_publisher_instance.send_message.assert_called_once_with(
            body=expected_body,
            exchange="update-projects.topic",
            routing_key="",
        )

    @override_settings(USE_EDA=True, TESTING=False)
    @patch("connect.usecases.project.eda_publisher.RabbitmqPublisher")
    def test_publish_project_status_updated_with_custom_timestamp(self, mock_rabbitmq):
        """Test publishing project status updated event with custom timestamp"""
        mock_publisher_instance = Mock()
        mock_rabbitmq.return_value = mock_publisher_instance

        publisher = ProjectEDAPublisher()

        custom_timestamp = pendulum.parse("2024-01-15T16:30:00Z")

        publisher.publish_project_status_updated(
            project_uuid=self.project_uuid,
            user_email=self.user_email,
            status="INACTIVE",
            updated_at=custom_timestamp,
        )

        expected_body = {
            "project_uuid": str(self.project_uuid),
            "action": "status_updated",
            "user_email": self.user_email,
            "status": "INACTIVE",
            "timestamp": custom_timestamp.to_iso8601_string(),
        }

        mock_publisher_instance.send_message.assert_called_once_with(
            body=expected_body,
            exchange="update-projects.topic",
            routing_key="",
        )

    @override_settings(USE_EDA=True, TESTING=False)
    @patch("connect.usecases.project.eda_publisher.RabbitmqPublisher")
    def test_publish_project_status_updated_with_in_test_status(self, mock_rabbitmq):
        """Test publishing project status updated event with IN_TEST status"""
        mock_publisher_instance = Mock()
        mock_rabbitmq.return_value = mock_publisher_instance

        publisher = ProjectEDAPublisher()

        custom_timestamp = pendulum.parse("2024-01-15T09:15:00Z")

        publisher.publish_project_status_updated(
            project_uuid=self.project_uuid,
            user_email=self.user_email,
            status="IN_TEST",
            updated_at=custom_timestamp,
        )

        expected_body = {
            "project_uuid": str(self.project_uuid),
            "action": "status_updated",
            "user_email": self.user_email,
            "status": "IN_TEST",
            "timestamp": custom_timestamp.to_iso8601_string(),
        }

        mock_publisher_instance.send_message.assert_called_once_with(
            body=expected_body,
            exchange="update-projects.topic",
            routing_key="",
        )

    @override_settings(USE_EDA=False, TESTING=False)
    def test_publish_project_status_updated_without_rabbitmq(self):
        """Test that publish_project_status_updated does nothing when rabbitmq_publisher is None"""
        publisher = ProjectEDAPublisher()

        # Should not raise any exception
        publisher.publish_project_status_updated(
            project_uuid=self.project_uuid,
            user_email=self.user_email,
            status="ACTIVE",
        )

    @override_settings(USE_EDA=True, TESTING=False)
    @patch("connect.usecases.project.eda_publisher.RabbitmqPublisher")
    def test_multiple_publishes_use_same_publisher_instance(self, mock_rabbitmq):
        """Test that multiple publish calls use the same RabbitmqPublisher instance"""
        mock_publisher_instance = Mock()
        mock_rabbitmq.return_value = mock_publisher_instance

        publisher = ProjectEDAPublisher()

        timestamp = pendulum.parse("2024-01-15T10:00:00Z")

        # Make multiple publish calls
        publisher.publish_project_deleted(
            project_uuid=self.project_uuid,
            user_email=self.user_email,
            deleted_at=timestamp,
        )

        publisher.publish_project_updated(
            project_uuid=self.project_uuid,
            user_email=self.user_email,
            name="Test",
            updated_at=timestamp,
        )

        publisher.publish_project_status_updated(
            project_uuid=self.project_uuid,
            user_email=self.user_email,
            status="ACTIVE",
            updated_at=timestamp,
        )

        # Verify RabbitmqPublisher was instantiated only once
        mock_rabbitmq.assert_called_once()

        # Verify send_message was called three times
        self.assertEqual(mock_publisher_instance.send_message.call_count, 3)

    @override_settings(USE_EDA=True, TESTING=False)
    @patch("connect.usecases.project.eda_publisher.RabbitmqPublisher")
    def test_exchange_name_is_correct_for_all_events(self, mock_rabbitmq):
        """Test that all events are published to the correct exchange"""
        mock_publisher_instance = Mock()
        mock_rabbitmq.return_value = mock_publisher_instance

        publisher = ProjectEDAPublisher()
        timestamp = pendulum.parse("2024-01-15T10:00:00Z")

        # Test deleted event
        publisher.publish_project_deleted(
            project_uuid=self.project_uuid,
            user_email=self.user_email,
            deleted_at=timestamp,
        )

        # Test updated event
        publisher.publish_project_updated(
            project_uuid=self.project_uuid,
            user_email=self.user_email,
            updated_at=timestamp,
        )

        # Test status updated event
        publisher.publish_project_status_updated(
            project_uuid=self.project_uuid,
            user_email=self.user_email,
            status="ACTIVE",
            updated_at=timestamp,
        )

        # Verify all calls used the correct exchange and empty routing key
        for call_args in mock_publisher_instance.send_message.call_args_list:
            self.assertEqual(call_args.kwargs["exchange"], "update-projects.topic")
            self.assertEqual(call_args.kwargs["routing_key"], "")

    @override_settings(USE_EDA=True, TESTING=False)
    @patch("connect.usecases.project.eda_publisher.RabbitmqPublisher")
    def test_uuid_is_converted_to_string_in_message_body(self, mock_rabbitmq):
        """Test that UUID is properly converted to string in message body"""
        mock_publisher_instance = Mock()
        mock_rabbitmq.return_value = mock_publisher_instance

        publisher = ProjectEDAPublisher()
        timestamp = pendulum.parse("2024-01-15T10:00:00Z")

        publisher.publish_project_deleted(
            project_uuid=self.project_uuid,
            user_email=self.user_email,
            deleted_at=timestamp,
        )

        call_args = mock_publisher_instance.send_message.call_args
        message_body = call_args.kwargs["body"]

        # Verify project_uuid is a string, not a UUID object
        self.assertIsInstance(message_body["project_uuid"], str)
        self.assertEqual(message_body["project_uuid"], str(self.project_uuid))
