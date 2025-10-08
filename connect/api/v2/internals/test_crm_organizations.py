import uuid
from datetime import datetime, timedelta
from unittest.mock import patch, Mock

from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from connect.api.v1.tests.utils import create_user_and_token
from connect.common.models import (
    Organization,
    OrganizationAuthorization,
    Project,
    ProjectAuthorization,
    ProjectRole,
    OrganizationRole,
    BillingPlan,
    TypeProject,
)
from connect.common.mocks import StripeMockGateway


@override_settings(USE_EDA_PERMISSIONS=False)
class CRMOrganizationViewSetTestCase(APITestCase):
    @patch("connect.authentication.signals.RabbitmqPublisher")
    @patch("connect.common.signals.RabbitmqPublisher")
    @patch("connect.common.signals.update_user_permission_project")
    @patch("connect.billing.get_gateway")
    def setUp(
        self,
        mock_get_gateway,
        mock_permission,
        mock_rabbitmq_common,
        mock_rabbitmq_auth,
    ):
        mock_get_gateway.return_value = StripeMockGateway()
        mock_permission.return_value = True
        mock_rabbitmq_common.return_value = Mock()
        mock_rabbitmq_auth.return_value = Mock()

        self.client = APIClient()
        self.crm_user, self.crm_token = create_user_and_token("crmuser")
        self.regular_user, self.regular_token = create_user_and_token("regularuser")

        # Create test organizations
        self.org1 = self._create_org("Test Organization 1", days_ago=10)
        self.org2 = self._create_org("Test Organization 2", days_ago=5)
        self.org3 = self._create_org("Test Organization 3", days_ago=1)

        self.project1 = self._create_project(
            "Project 1", self.org1, "vtex-account-1", TypeProject.COMMERCE
        )
        self.project2 = self._create_project(
            "Project 2", self.org1, "", TypeProject.GENERAL
        )
        self.project3 = self._create_project(
            "Project 3", self.org2, "vtex-account-2", TypeProject.COMMERCE
        )
        self.project4 = self._create_project(
            "Project 4", self.org3, None, TypeProject.GENERAL
        )

        self._create_auth_data()
        self.list_url = reverse("crm-organizations-list")

    def _create_org(self, name, days_ago):
        return Organization.objects.create(
            name=name,
            description=f"{name} description",
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
            created_at=datetime.now() - timedelta(days=days_ago),
        )

    def _create_project(self, name, org, vtex_account, project_type):
        kwargs = {
            "name": name,
            "organization": org,
            "flow_organization": uuid.uuid4(),
            "project_type": project_type,
        }
        if vtex_account is not None:
            kwargs["vtex_account"] = vtex_account
        return Project.objects.create(**kwargs)

    def _create_auth_data(self):
        self.org1_auth = OrganizationAuthorization.objects.create(
            user=self.crm_user,
            organization=self.org1,
            role=OrganizationRole.ADMIN.value,
        )
        self.org1_auth_regular = OrganizationAuthorization.objects.create(
            user=self.regular_user,
            organization=self.org1,
            role=OrganizationRole.VIEWER.value,
        )
        OrganizationAuthorization.objects.create(
            user=self.regular_user,
            organization=self.org2,
            role=OrganizationRole.NOT_SETTED.value,
        )
        self.org2_auth = OrganizationAuthorization.objects.create(
            user=self.crm_user,
            organization=self.org2,
            role=OrganizationRole.CONTRIBUTOR.value,
        )

        ProjectAuthorization.objects.create(
            user=self.crm_user,
            project=self.project1,
            role=ProjectRole.MODERATOR.value,
            organization_authorization=self.org1_auth,
        )
        ProjectAuthorization.objects.create(
            user=self.regular_user,
            project=self.project1,
            role=ProjectRole.NOT_SETTED.value,
            organization_authorization=self.org1_auth_regular,
        )
        ProjectAuthorization.objects.create(
            user=self.crm_user,
            project=self.project3,
            role=ProjectRole.CONTRIBUTOR.value,
            organization_authorization=self.org2_auth,
        )

    def _auth_as_crm(self):
        self.client.force_authenticate(user=self.crm_user)

    # Permission Tests
    @override_settings(ALLOW_CRM_ACCESS=True, CRM_EMAILS_LIST=["crmuser@user.com"])
    def test_crm_user_can_access(self):
        self._auth_as_crm()
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)

    @override_settings(ALLOW_CRM_ACCESS=True, CRM_EMAILS_LIST=["crmuser@user.com"])
    def test_non_crm_user_forbidden(self):
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @override_settings(ALLOW_CRM_ACCESS=False, CRM_EMAILS_LIST=["crmuser@user.com"])
    def test_crm_access_disabled(self):
        self._auth_as_crm()
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_user_denied(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # Structure Tests
    @override_settings(ALLOW_CRM_ACCESS=True, CRM_EMAILS_LIST=["crmuser@user.com"])
    def test_response_structure(self):
        self._auth_as_crm()
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        for field in ["next", "previous", "results"]:
            self.assertIn(field, response.data)

        results = response.data["results"]
        self.assertGreater(len(results), 0)

        org = results[0]
        for field in ["uuid", "name", "created_at", "users", "projects"]:
            self.assertIn(field, org)

        if org["users"]:
            user = org["users"][0]
            for field in ["email", "first_name", "last_name", "role", "role_name"]:
                self.assertIn(field, user)

        if org["projects"]:
            project = org["projects"][0]
            for field in ["name", "uuid", "vtex_account"]:
                self.assertIn(field, project)
            self.assertNotIn("users", project)

    # Filter Tests
    @override_settings(ALLOW_CRM_ACCESS=True, CRM_EMAILS_LIST=["crmuser@user.com"])
    def test_filter_by_organization_uuid(self):
        self._auth_as_crm()
        response = self.client.get(
            self.list_url, {"organization_uuid": str(self.org1.uuid)}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["uuid"], str(self.org1.uuid))

    @override_settings(ALLOW_CRM_ACCESS=True, CRM_EMAILS_LIST=["crmuser@user.com"])
    def test_filter_by_project_uuid_returns_all_org_projects(self):
        self._auth_as_crm()
        response = self.client.get(
            self.list_url, {"project_uuid": str(self.project1.uuid)}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["uuid"], str(self.org1.uuid))

        # Should return all projects from the organization, not just the filtered one
        projects = results[0]["projects"]
        self.assertEqual(len(projects), 2)  # org1 has project1 and project2
        project_uuids = [p["uuid"] for p in projects]
        self.assertIn(str(self.project1.uuid), project_uuids)
        self.assertIn(str(self.project2.uuid), project_uuids)

    @override_settings(ALLOW_CRM_ACCESS=True, CRM_EMAILS_LIST=["crmuser@user.com"])
    def test_filter_project_uuid_not_found(self):
        self._auth_as_crm()
        response = self.client.get(self.list_url, {"project_uuid": str(uuid.uuid4())})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @override_settings(ALLOW_CRM_ACCESS=True, CRM_EMAILS_LIST=["crmuser@user.com"])
    def test_filter_project_uuid_invalid_format(self):
        self._auth_as_crm()
        response = self.client.get(self.list_url, {"project_uuid": "invalid-uuid"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(ALLOW_CRM_ACCESS=True, CRM_EMAILS_LIST=["crmuser@user.com"])
    def test_filter_has_vtex_account_true(self):
        self._auth_as_crm()
        response = self.client.get(self.list_url, {"has_vtex_account": "true"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]

        org_uuids = [org["uuid"] for org in results]
        self.assertIn(str(self.org1.uuid), org_uuids)
        self.assertIn(str(self.org2.uuid), org_uuids)
        self.assertNotIn(str(self.org3.uuid), org_uuids)

    @override_settings(ALLOW_CRM_ACCESS=True, CRM_EMAILS_LIST=["crmuser@user.com"])
    def test_filter_has_vtex_account_false(self):
        self._auth_as_crm()
        response = self.client.get(self.list_url, {"has_vtex_account": "false"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]

        org_uuids = [org["uuid"] for org in results]
        self.assertIn(str(self.org3.uuid), org_uuids)

    @override_settings(ALLOW_CRM_ACCESS=True, CRM_EMAILS_LIST=["crmuser@user.com"])
    def test_filter_by_date_range(self):
        self._auth_as_crm()
        yesterday = (datetime.now() - timedelta(days=2)).strftime("%d-%m-%Y")
        response = self.client.get(self.list_url, {"created_after": yesterday})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]

        org_uuids = [org["uuid"] for org in results]
        self.assertIn(str(self.org3.uuid), org_uuids)

    @override_settings(ALLOW_CRM_ACCESS=True, CRM_EMAILS_LIST=["crmuser@user.com"])
    def test_filter_invalid_date_format(self):
        self._auth_as_crm()
        response = self.client.get(self.list_url, {"created_after": "2024-01-15"})
        self.assertIn(
            response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_200_OK]
        )

    @override_settings(ALLOW_CRM_ACCESS=True, CRM_EMAILS_LIST=["crmuser@user.com"])
    def test_combined_filters(self):
        self._auth_as_crm()
        response = self.client.get(
            self.list_url,
            {"has_vtex_account": "true", "organization_uuid": str(self.org1.uuid)},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["uuid"], str(self.org1.uuid))

    # Data Validation Tests
    @override_settings(ALLOW_CRM_ACCESS=True, CRM_EMAILS_LIST=["crmuser@user.com"])
    def test_exclude_not_setted_roles(self):
        self._auth_as_crm()
        response = self.client.get(
            self.list_url, {"organization_uuid": str(self.org1.uuid)}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]

        org = results[0]
        users = org["users"]
        user_emails = [user["email"] for user in users]
        self.assertIn("crmuser@user.com", user_emails)
        self.assertIn("regularuser@user.com", user_emails)

        for user in users:
            self.assertNotEqual(user["role"], OrganizationRole.NOT_SETTED.value)
            self.assertIsNotNone(user["role_name"])

    @override_settings(ALLOW_CRM_ACCESS=True, CRM_EMAILS_LIST=["crmuser@user.com"])
    def test_retrieve_specific_organization(self):
        self._auth_as_crm()
        detail_url = reverse(
            "crm-organizations-detail", kwargs={"uuid": self.org1.uuid}
        )
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(response.data["uuid"], str(self.org1.uuid))
        self.assertEqual(response.data["name"], self.org1.name)

        projects = response.data["projects"]
        project_names = [p["name"] for p in projects]
        self.assertIn("Project 1", project_names)
        self.assertIn("Project 2", project_names)

    @override_settings(ALLOW_CRM_ACCESS=True, CRM_EMAILS_LIST=["crmuser@user.com"])
    def test_pagination(self):
        self._auth_as_crm()
        response = self.client.get(self.list_url, {"page_size": 1})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        for field in ["next", "previous", "results"]:
            self.assertIn(field, response.data)

        results = response.data["results"]
        self.assertEqual(len(results), 1)

    @override_settings(ALLOW_CRM_ACCESS=True, CRM_EMAILS_LIST=["crmuser@user.com"])
    def test_ordering(self):
        self._auth_as_crm()
        response = self.client.get(self.list_url, {"ordering": "-created_at"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        results = response.data["results"]
        if len(results) > 1:
            created_dates = [org["created_at"] for org in results]
            self.assertEqual(created_dates, sorted(created_dates, reverse=True))

    @override_settings(ALLOW_CRM_ACCESS=True, CRM_EMAILS_LIST=["crmuser@user.com"])
    def test_vtex_account_field_handling(self):
        self._auth_as_crm()
        response = self.client.get(
            self.list_url, {"organization_uuid": str(self.org1.uuid)}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]

        org = results[0]
        projects = org["projects"]

        project1_data = next(p for p in projects if p["name"] == "Project 1")
        project2_data = next(p for p in projects if p["name"] == "Project 2")

        self.assertEqual(project1_data["vtex_account"], "vtex-account-1")
        self.assertEqual(project2_data["vtex_account"], "")

    @override_settings(ALLOW_CRM_ACCESS=True, CRM_EMAILS_LIST=["crmuser@user.com"])
    def test_method_not_allowed(self):
        self._auth_as_crm()

        response = self.client.post(self.list_url, {})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        detail_url = reverse(
            "crm-organizations-detail", kwargs={"uuid": self.org1.uuid}
        )
        response = self.client.put(detail_url, {})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
