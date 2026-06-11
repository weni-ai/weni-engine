import uuid

from django.test import TestCase, override_settings
from unittest.mock import patch

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
from connect.usecases.project.list_authorized_projects import (
    ListAuthorizedProjectsUseCase,
)


@override_settings(USE_EDA_PERMISSIONS=False)
class ListAuthorizedProjectsUseCaseTestCase(TestCase):
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

        self.user, _ = create_user_and_token("list_uc_user")

        self.org = Organization.objects.create(
            name="UC List Org",
            description="Org for list use case tests",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        self.org_auth = self.org.authorizations.create(
            user=self.user, role=OrganizationRole.ADMIN.value
        )

        self.authorized_project = Project.objects.create(
            name="Authorized Project",
            flow_organization=uuid.uuid4(),
            organization=self.org,
        )
        self.foreign_project = Project.objects.create(
            name="Foreign Project",
            flow_organization=uuid.uuid4(),
            organization=self.org,
        )

        # Project creation auto-grants authorizations to org contributors.
        # Reset to an explicit state: the user is authorized only to one project.
        ProjectAuthorization.objects.filter(user=self.user).delete()
        ProjectAuthorization.objects.create(
            user=self.user,
            project=self.authorized_project,
            role=ProjectRole.CONTRIBUTOR.value,
            organization_authorization=self.org_auth,
        )

        self.use_case = ListAuthorizedProjectsUseCase()

    def _executed_uuids(self, organization_uuid=None):
        return set(
            self.use_case.execute(
                user=self.user, organization_uuid=organization_uuid
            ).values_list("uuid", flat=True)
        )

    def test_execute_returns_only_authorized_projects(self):
        uuids = self._executed_uuids()

        self.assertIn(self.authorized_project.uuid, uuids)
        self.assertNotIn(self.foreign_project.uuid, uuids)

    def test_execute_excludes_not_setted_role(self):
        ProjectAuthorization.objects.create(
            user=self.user,
            project=self.foreign_project,
            role=ProjectRole.NOT_SETTED.value,
            organization_authorization=self.org_auth,
        )

        self.assertNotIn(self.foreign_project.uuid, self._executed_uuids())

    def test_execute_scopes_role_per_user(self):
        other_user, _ = create_user_and_token("other_list_uc_user")
        other_org_auth = self.org.authorizations.create(
            user=other_user, role=OrganizationRole.ADMIN.value
        )
        ProjectAuthorization.objects.create(
            user=other_user,
            project=self.authorized_project,
            role=ProjectRole.NOT_SETTED.value,
            organization_authorization=other_org_auth,
        )

        uuids = self._executed_uuids()

        self.assertIn(self.authorized_project.uuid, uuids)
        self.assertNotIn(self.foreign_project.uuid, uuids)

    def test_execute_filters_by_organization(self):
        in_scope = self._executed_uuids(organization_uuid=str(self.org.uuid))
        out_of_scope = self._executed_uuids(organization_uuid=str(uuid.uuid4()))

        self.assertIn(self.authorized_project.uuid, in_scope)
        self.assertEqual(out_of_scope, set())
