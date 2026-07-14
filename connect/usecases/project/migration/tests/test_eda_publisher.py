import uuid
from unittest.mock import Mock, patch

import pendulum
from django.test import TestCase, override_settings

from connect.usecases.project.migration.eda_publisher import (
    ProjectMigrationEDAPublisher,
)


class ProjectMigrationEDAPublisherTestCase(TestCase):
    def setUp(self):
        self.event_id = uuid.uuid4()
        self.project_uuid = uuid.uuid4()
        self.org_from = uuid.uuid4()
        self.org_to = uuid.uuid4()

    @override_settings(USE_PROJECT_MIGRATION_PUBLISHER=True, TESTING=False)
    @patch("connect.usecases.project.migration.eda_publisher.EDAPublisher")
    def test_publisher_initialization_when_enabled(self, mock_eda):
        publisher = ProjectMigrationEDAPublisher()

        mock_eda.assert_called_once()
        self.assertIsNotNone(publisher.eda_publisher)

    @override_settings(USE_PROJECT_MIGRATION_PUBLISHER=False, TESTING=False)
    def test_publisher_initialization_when_disabled(self):
        publisher = ProjectMigrationEDAPublisher()
        self.assertIsNone(publisher.eda_publisher)

    @override_settings(USE_PROJECT_MIGRATION_PUBLISHER=True, TESTING=True)
    def test_publisher_initialization_when_testing(self):
        publisher = ProjectMigrationEDAPublisher()
        self.assertIsNone(publisher.eda_publisher)

    @override_settings(USE_PROJECT_MIGRATION_PUBLISHER=True, TESTING=False)
    @patch("connect.usecases.project.migration.eda_publisher.EDAPublisher")
    def test_publish_project_migrated_envelope(self, mock_eda):
        mock_instance = Mock()
        mock_eda.return_value = mock_instance
        publisher = ProjectMigrationEDAPublisher()
        timestamp = pendulum.parse("2026-05-20T11:15:00Z")

        publisher.publish_project_migrated(
            event_id=self.event_id,
            project_uuid=self.project_uuid,
            org_from=self.org_from,
            org_to=self.org_to,
            timestamp=timestamp,
        )

        expected_body = {
            "event_id": str(self.event_id),
            "event_type": "engine.project.migrated",
            "producer": "weni-engine",
            "timestamp": timestamp.to_iso8601_string(),
            "data": {
                "uuid": str(self.project_uuid),
                "org": {
                    "from": str(self.org_from),
                    "to": str(self.org_to),
                },
            },
        }
        mock_instance.send_message.assert_called_once_with(
            expected_body,
            exchange="projects.topic",
            routing_key="project.migrated",
        )

    @override_settings(USE_PROJECT_MIGRATION_PUBLISHER=False, TESTING=False)
    def test_publish_noop_when_disabled(self):
        publisher = ProjectMigrationEDAPublisher()
        publisher.publish_project_migrated(
            event_id=self.event_id,
            project_uuid=self.project_uuid,
            org_from=self.org_from,
            org_to=self.org_to,
        )
