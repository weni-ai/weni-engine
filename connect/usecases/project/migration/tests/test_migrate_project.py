import uuid
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
    ProjectMigration,
    ProjectMigrationStatus,
    ProjectRole,
)
from connect.usecases.project.exceptions import (
    OrganizationNotFoundError,
    ProjectMigrationNotFoundError,
    ProjectMigrationRepublishError,
    ProjectNotFoundError,
    SameOrganizationMigrationError,
)
from connect.usecases.project.migration.migrate_project import (
    MODULE_STATUS_ERROR,
    MODULE_STATUS_SUCCESS,
    MigrateProjectUseCase,
)


@override_settings(USE_EDA_PERMISSIONS=False, USE_PROJECT_MIGRATION_PUBLISHER=False)
class MigrateProjectUseCaseTestCase(TestCase):
    @patch("connect.common.signals.update_user_permission_project")
    @patch("connect.billing.get_gateway")
    @patch(
        "connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.update_user_permission_project"
    )
    @patch(
        "connect.api.v1.internal.integrations.integrations_rest_client.IntegrationsRESTClient.update_user_permission_project"
    )
    def setUp(self, integrations_rest, flows_rest, mock_get_gateway, mock_permission):
        integrations_rest.side_effect = [200, 200]
        flows_rest.side_effect = [200, 200]
        mock_get_gateway.return_value = StripeMockGateway()
        mock_permission.return_value = True

        self.user, _ = create_user_and_token("migration_uc_user")
        self.other_user, _ = create_user_and_token("migration_uc_other")

        self.org_from = Organization.objects.create(
            name="Source Org",
            description="Source",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        self.org_to = Organization.objects.create(
            name="Destination Org",
            description="Destination",
            inteligence_organization=2,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )

        self.org_from_auth = self.org_from.authorizations.create(
            user=self.user, role=OrganizationRole.ADMIN.value
        )
        self.org_to_auth = self.org_to.authorizations.create(
            user=self.user, role=OrganizationRole.ADMIN.value
        )
        self.org_from.authorizations.create(
            user=self.other_user, role=OrganizationRole.CONTRIBUTOR.value
        )

        self.project = Project.objects.create(
            name="Migratable Project",
            flow_organization=uuid.uuid4(),
            organization=self.org_from,
        )

        ProjectAuthorization.objects.filter(project=self.project).delete()
        ProjectAuthorization.objects.create(
            user=self.user,
            project=self.project,
            role=ProjectRole.MODERATOR.value,
            organization_authorization=self.org_from_auth,
        )
        ProjectAuthorization.objects.create(
            user=self.other_user,
            project=self.project,
            role=ProjectRole.CONTRIBUTOR.value,
            organization_authorization=self.org_from.authorizations.get(
                user=self.other_user
            ),
        )

        self.mock_publisher = Mock()
        self.use_case = MigrateProjectUseCase(publisher=self.mock_publisher)

    def test_execute_reassigns_organization_and_publishes(self):
        with self.captureOnCommitCallbacks(execute=True):
            migration = self.use_case.execute(
                project_uuid=self.project.uuid,
                org_to_uuid=self.org_to.uuid,
                requested_by=self.user.email,
            )

        self.project.refresh_from_db()
        migration.refresh_from_db()

        self.assertEqual(self.project.organization_id, self.org_to.uuid)
        self.assertEqual(migration.org_from, self.org_from.uuid)
        self.assertEqual(migration.org_to, self.org_to.uuid)
        self.assertEqual(migration.status, ProjectMigrationStatus.IN_PROGRESS)
        self.assertIsNotNone(migration.published_at)
        self.assertEqual(migration.requested_by, self.user.email)

        self.mock_publisher.publish_project_migrated.assert_called_once_with(
            event_id=migration.uuid,
            project_uuid=self.project.uuid,
            org_from=self.org_from.uuid,
            org_to=self.org_to.uuid,
        )

    def test_execute_reconciles_authorizations(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.use_case.execute(
                project_uuid=self.project.uuid,
                org_to_uuid=self.org_to.uuid,
            )

        remaining = ProjectAuthorization.objects.filter(project=self.project)
        self.assertEqual(remaining.count(), 1)
        auth = remaining.get()
        self.assertEqual(auth.user, self.user)
        self.assertEqual(auth.organization_authorization_id, self.org_to_auth.uuid)
        self.assertFalse(
            ProjectAuthorization.objects.filter(
                project=self.project, user=self.other_user
            ).exists()
        )

    def test_reconcile_authorizations_batches_org_auth_lookup(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as captured:
            MigrateProjectUseCase(
                publisher=self.mock_publisher
            )._reconcile_project_authorizations(
                project=self.project,
                org_to=self.org_to,
            )

        org_auth_queries = [
            query["sql"]
            for query in captured.captured_queries
            if 'FROM "common_organizationauthorization"' in query["sql"]
        ]
        self.assertEqual(len(org_auth_queries), 1)
        self.assertIn("IN (", org_auth_queries[0])

    def test_execute_is_idempotent_for_active_migration(self):
        with self.captureOnCommitCallbacks(execute=True):
            first = self.use_case.execute(
                project_uuid=self.project.uuid,
                org_to_uuid=self.org_to.uuid,
            )
            second = self.use_case.execute(
                project_uuid=self.project.uuid,
                org_to_uuid=self.org_to.uuid,
            )

        self.assertEqual(first.uuid, second.uuid)
        self.assertEqual(ProjectMigration.objects.count(), 1)
        self.assertEqual(self.mock_publisher.publish_project_migrated.call_count, 1)

    def test_execute_rejects_same_organization(self):
        with self.assertRaises(SameOrganizationMigrationError):
            self.use_case.execute(
                project_uuid=self.project.uuid,
                org_to_uuid=self.org_from.uuid,
            )

    def test_execute_raises_project_not_found(self):
        with self.assertRaises(ProjectNotFoundError):
            self.use_case.execute(
                project_uuid=uuid.uuid4(),
                org_to_uuid=self.org_to.uuid,
            )

    def test_execute_raises_organization_not_found(self):
        with self.assertRaises(OrganizationNotFoundError):
            self.use_case.execute(
                project_uuid=self.project.uuid,
                org_to_uuid=uuid.uuid4(),
            )

    def test_publish_failure_marks_publish_failed(self):
        self.mock_publisher.publish_project_migrated.side_effect = RuntimeError(
            "broker"
        )

        with self.captureOnCommitCallbacks(execute=True):
            migration = self.use_case.execute(
                project_uuid=self.project.uuid,
                org_to_uuid=self.org_to.uuid,
            )

        migration.refresh_from_db()
        self.assertEqual(migration.status, ProjectMigrationStatus.PUBLISH_FAILED)
        self.assertIsNone(migration.published_at)

    def test_republish_after_publish_failed(self):
        self.mock_publisher.publish_project_migrated.side_effect = [
            RuntimeError("broker"),
            None,
        ]

        with self.captureOnCommitCallbacks(execute=True):
            migration = self.use_case.execute(
                project_uuid=self.project.uuid,
                org_to_uuid=self.org_to.uuid,
            )

        migration.refresh_from_db()
        self.assertEqual(migration.status, ProjectMigrationStatus.PUBLISH_FAILED)

        republished = self.use_case.republish(event_id=migration.uuid)
        self.assertEqual(republished.status, ProjectMigrationStatus.IN_PROGRESS)
        self.assertIsNotNone(republished.published_at)
        self.assertEqual(self.mock_publisher.publish_project_migrated.call_count, 2)

    def test_republish_rejects_non_failed_status(self):
        with self.captureOnCommitCallbacks(execute=True):
            migration = self.use_case.execute(
                project_uuid=self.project.uuid,
                org_to_uuid=self.org_to.uuid,
            )

        with self.assertRaises(ProjectMigrationRepublishError):
            self.use_case.republish(event_id=migration.uuid)

    @override_settings(PROJECT_MIGRATION_EXPECTED_MODULES=["billing", "flows"])
    def test_register_module_status_recomputes_completed(self):
        with self.captureOnCommitCallbacks(execute=True):
            migration = self.use_case.execute(
                project_uuid=self.project.uuid,
                org_to_uuid=self.org_to.uuid,
            )

        self.use_case.register_module_status(
            event_id=migration.uuid,
            module="billing",
            status=MODULE_STATUS_SUCCESS,
        )
        migration = self.use_case.register_module_status(
            event_id=migration.uuid,
            module="flows",
            status=MODULE_STATUS_SUCCESS,
        )

        self.assertEqual(migration.status, ProjectMigrationStatus.COMPLETED)
        self.assertEqual(
            migration.modules_status["billing"]["status"], MODULE_STATUS_SUCCESS
        )
        self.assertEqual(
            migration.modules_status["flows"]["status"], MODULE_STATUS_SUCCESS
        )

    @override_settings(PROJECT_MIGRATION_EXPECTED_MODULES=["billing", "flows"])
    def test_register_module_status_partial_error(self):
        with self.captureOnCommitCallbacks(execute=True):
            migration = self.use_case.execute(
                project_uuid=self.project.uuid,
                org_to_uuid=self.org_to.uuid,
            )

        self.use_case.register_module_status(
            event_id=migration.uuid,
            module="billing",
            status=MODULE_STATUS_SUCCESS,
        )
        migration = self.use_case.register_module_status(
            event_id=migration.uuid,
            module="flows",
            status=MODULE_STATUS_ERROR,
            error="timeout",
        )

        self.assertEqual(migration.status, ProjectMigrationStatus.PARTIAL_ERROR)
        self.assertEqual(migration.modules_status["flows"]["error"], "timeout")

    def test_register_module_status_not_found(self):
        with self.assertRaises(ProjectMigrationNotFoundError):
            self.use_case.register_module_status(
                event_id=uuid.uuid4(),
                module="billing",
                status=MODULE_STATUS_SUCCESS,
            )
