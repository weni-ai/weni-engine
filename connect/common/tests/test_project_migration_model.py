import uuid

from django.test import TestCase

from connect.common.models import (
    BillingPlan,
    Organization,
    Project,
    ProjectMigration,
    ProjectMigrationStatus,
)


class ProjectMigrationModelTestCase(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="Migration Model Org",
            description="Migration Model Org",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        self.project = Project.objects.create(
            name="Migration Model Project",
            flow_organization=uuid.uuid4(),
            organization=self.organization,
        )

    def test_str_representation(self):
        migration = ProjectMigration.objects.create(
            project=self.project,
            org_from=self.organization.uuid,
            org_to=uuid.uuid4(),
            status=ProjectMigrationStatus.IN_PROGRESS,
        )

        self.assertEqual(
            str(migration),
            f"ProjectMigration {migration.uuid} ({ProjectMigrationStatus.IN_PROGRESS})",
        )

    def test_is_active_is_false_when_completed(self):
        migration = ProjectMigration.objects.create(
            project=self.project,
            org_from=self.organization.uuid,
            org_to=uuid.uuid4(),
            status=ProjectMigrationStatus.COMPLETED,
        )

        self.assertFalse(migration.is_active)

    def test_is_active_is_true_for_non_completed_status(self):
        migration = ProjectMigration.objects.create(
            project=self.project,
            org_from=self.organization.uuid,
            org_to=uuid.uuid4(),
            status=ProjectMigrationStatus.PARTIAL_ERROR,
        )

        self.assertTrue(migration.is_active)
