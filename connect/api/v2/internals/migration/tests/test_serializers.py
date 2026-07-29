import uuid

from django.test import TestCase
from rest_framework.exceptions import ValidationError

from connect.api.v2.internals.migration.serializers import (
    ProjectMigrationCreateSerializer,
    ProjectMigrationModuleStatusSerializer,
    ProjectMigrationSerializer,
)
from connect.common.models import (
    BillingPlan,
    Organization,
    Project,
    ProjectMigration,
    ProjectMigrationStatus,
)
from connect.usecases.project.migration.migrate_project import MODULE_STATUS_ERROR


class ProjectMigrationSerializersTestCase(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="Serializer Org",
            description="Serializer Org",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        self.project = Project.objects.create(
            name="Serializer Project",
            flow_organization=uuid.uuid4(),
            organization=self.organization,
        )

    def test_create_serializer_accepts_valid_payload(self):
        serializer = ProjectMigrationCreateSerializer(
            data={
                "project_uuid": str(self.project.uuid),
                "org_to": str(uuid.uuid4()),
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["project_uuid"], self.project.uuid)

    def test_create_serializer_rejects_invalid_payload(self):
        serializer = ProjectMigrationCreateSerializer(data={"org_to": "not-a-uuid"})

        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)

    def test_module_status_serializer_accepts_optional_error(self):
        serializer = ProjectMigrationModuleStatusSerializer(
            data={
                "module": "billing",
                "status": MODULE_STATUS_ERROR,
                "error": "timeout",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["error"], "timeout")

    def test_module_status_serializer_rejects_invalid_status(self):
        serializer = ProjectMigrationModuleStatusSerializer(
            data={"module": "billing", "status": "pending"}
        )

        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)

    def test_model_serializer_exposes_event_and_project_uuid(self):
        migration = ProjectMigration.objects.create(
            project=self.project,
            org_from=self.organization.uuid,
            org_to=uuid.uuid4(),
            status=ProjectMigrationStatus.IN_PROGRESS,
            requested_by="ops@example.com",
        )

        data = ProjectMigrationSerializer(migration).data

        self.assertEqual(data["event_id"], str(migration.uuid))
        self.assertEqual(data["project_uuid"], str(self.project.uuid))
        self.assertEqual(data["requested_by"], "ops@example.com")
