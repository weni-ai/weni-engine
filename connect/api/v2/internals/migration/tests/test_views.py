import json
import uuid
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from connect.api.v1.tests.utils import create_user_and_token
from connect.api.v2.internals.migration.views import (
    ProjectMigrationCreateView,
    ProjectMigrationDetailView,
    ProjectMigrationRepublishView,
    ProjectMigrationStatusView,
)
from connect.common.mocks import StripeMockGateway
from connect.common.models import (
    BillingPlan,
    Organization,
    OrganizationRole,
    Project,
    ProjectMigration,
    ProjectMigrationStatus,
)
from connect.usecases.project.migration.migrate_project import (
    MODULE_STATUS_ERROR,
    MODULE_STATUS_SUCCESS,
    MigrateProjectUseCase,
)


@override_settings(USE_EDA_PERMISSIONS=False, USE_PROJECT_MIGRATION_PUBLISHER=False)
class ProjectMigrationViewsTestCase(TestCase):
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

        self.factory = APIRequestFactory()
        self.user, _ = create_user_and_token("migration_view_user")

        self.org_from = Organization.objects.create(
            name="View Source Org",
            description="Source",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        self.org_to = Organization.objects.create(
            name="View Dest Org",
            description="Destination",
            inteligence_organization=2,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        self.org_from.authorizations.create(
            user=self.user, role=OrganizationRole.ADMIN.value
        )
        self.org_to.authorizations.create(
            user=self.user, role=OrganizationRole.ADMIN.value
        )
        self.project = Project.objects.create(
            name="View Migratable Project",
            flow_organization=uuid.uuid4(),
            organization=self.org_from,
        )

    @patch("connect.api.v1.internal.permissions.ModuleHasPermission.has_permission")
    def test_create_migration(self, module_has_permission):
        module_has_permission.return_value = True
        mock_publisher = Mock()
        use_case = MigrateProjectUseCase(publisher=mock_publisher)

        with patch(
            "connect.api.v2.internals.migration.views.MigrateProjectUseCase",
            return_value=use_case,
        ):
            request = self.factory.post(
                "/v2/internals/connect/project-migrations",
                {
                    "project_uuid": str(self.project.uuid),
                    "org_to": str(self.org_to.uuid),
                },
                format="json",
            )
            force_authenticate(request, user=self.user)

            with self.captureOnCommitCallbacks(execute=True):
                response = ProjectMigrationCreateView.as_view()(request)
            response.render()

        content = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Response body is built before on_commit runs; re-read from DB.
        migration = ProjectMigration.objects.get(uuid=content["event_id"])
        self.assertEqual(migration.status, ProjectMigrationStatus.IN_PROGRESS)
        self.assertEqual(content["project_uuid"], str(self.project.uuid))
        self.assertEqual(content["org_from"], str(self.org_from.uuid))
        self.assertEqual(content["org_to"], str(self.org_to.uuid))
        self.assertIn("event_id", content)

        self.project.refresh_from_db()
        self.assertEqual(self.project.organization_id, self.org_to.uuid)
        mock_publisher.publish_project_migrated.assert_called_once()

    @patch("connect.api.v1.internal.permissions.ModuleHasPermission.has_permission")
    def test_get_migration(self, module_has_permission):
        module_has_permission.return_value = True
        migration = ProjectMigration.objects.create(
            project=self.project,
            org_from=self.org_from.uuid,
            org_to=self.org_to.uuid,
            status=ProjectMigrationStatus.IN_PROGRESS,
            modules_status={"billing": {"status": MODULE_STATUS_SUCCESS}},
        )

        request = self.factory.get(
            f"/v2/internals/connect/project-migrations/{migration.uuid}"
        )
        force_authenticate(request, user=self.user)
        response = ProjectMigrationDetailView.as_view()(
            request, event_id=migration.uuid
        )
        response.render()
        content = json.loads(response.content)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(content["event_id"], str(migration.uuid))
        self.assertEqual(
            content["modules_status"]["billing"]["status"], MODULE_STATUS_SUCCESS
        )

    @patch("connect.api.v1.internal.permissions.ModuleHasPermission.has_permission")
    @override_settings(PROJECT_MIGRATION_EXPECTED_MODULES=["billing"])
    def test_register_module_status(self, module_has_permission):
        module_has_permission.return_value = True
        migration = ProjectMigration.objects.create(
            project=self.project,
            org_from=self.org_from.uuid,
            org_to=self.org_to.uuid,
            status=ProjectMigrationStatus.IN_PROGRESS,
        )

        request = self.factory.post(
            f"/v2/internals/connect/project-migrations/{migration.uuid}/status",
            {
                "module": "billing",
                "status": MODULE_STATUS_ERROR,
                "error": "db unavailable",
            },
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = ProjectMigrationStatusView.as_view()(
            request, event_id=migration.uuid
        )
        response.render()
        content = json.loads(response.content)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(content["status"], ProjectMigrationStatus.PARTIAL_ERROR)
        self.assertEqual(
            content["modules_status"]["billing"]["error"], "db unavailable"
        )

    @patch("connect.api.v1.internal.permissions.ModuleHasPermission.has_permission")
    def test_republish(self, module_has_permission):
        module_has_permission.return_value = True
        migration = ProjectMigration.objects.create(
            project=self.project,
            org_from=self.org_from.uuid,
            org_to=self.org_to.uuid,
            status=ProjectMigrationStatus.PUBLISH_FAILED,
        )
        mock_publisher = Mock()

        with patch(
            "connect.api.v2.internals.migration.views.MigrateProjectUseCase",
            return_value=MigrateProjectUseCase(publisher=mock_publisher),
        ):
            request = self.factory.post(
                f"/v2/internals/connect/project-migrations/{migration.uuid}/republish",
                {},
                format="json",
            )
            force_authenticate(request, user=self.user)
            response = ProjectMigrationRepublishView.as_view()(
                request, event_id=migration.uuid
            )
            response.render()

        content = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(content["status"], ProjectMigrationStatus.IN_PROGRESS)
        mock_publisher.publish_project_migrated.assert_called_once()

    @patch("connect.api.v1.internal.permissions.ModuleHasPermission.has_permission")
    def test_create_requires_module_permission(self, module_has_permission):
        module_has_permission.return_value = False

        request = self.factory.post(
            "/v2/internals/connect/project-migrations",
            {
                "project_uuid": str(self.project.uuid),
                "org_to": str(self.org_to.uuid),
            },
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = ProjectMigrationCreateView.as_view()(request)
        response.render()

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
