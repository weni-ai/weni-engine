import uuid
from unittest.mock import patch, Mock

from django.test import override_settings
from django.urls import reverse
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from connect.api.v1.tests.utils import create_user_and_token
from connect.authentication.models import User
from connect.common.models import (
    Organization,
    OrganizationAuthorization,
    Project,
    ProjectAuthorization,
    OrganizationRole,
    RequestPermissionOrganization,
    BillingPlan,
    TypeProject,
)
from connect.common.mocks import StripeMockGateway
from connect.usecases.commerce.create_vtex_project import CreateVtexProjectUseCase
from connect.usecases.commerce.dto import CreateVtexProjectDTO
from connect.usecases.commerce.set_vtex_host_store import SetVtexHostStoreUseCase


@override_settings(USE_EDA_PERMISSIONS=False)  # Disable EDA to avoid RabbitMQ issues
class CreateVtexProjectViewTestCase(APITestCase):
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
        self.user, self.token = create_user_and_token("testuser")

        # Add permission for internal communication (module-to-module)
        content_type = ContentType.objects.get_for_model(User)
        permission, _ = Permission.objects.get_or_create(
            codename="can_communicate_internally",
            name="can communicate internally",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        # Authenticate the client
        self.client.force_authenticate(user=self.user)

        self.url = reverse("create-vtex-project")

    def test_create_new_project_successfully(self):
        """Full creation flow: existing user, new org, new project.
        Verifies the endpoint returns 200 with project_uuid and user_uuid."""
        response = self.client.post(
            self.url,
            {
                "user_email": self.user.email,
                "vtex_account": "newstore",
                "language": "pt-br",
                "organization_name": "New Store Org",
                "project_name": "New Store Project",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("project_uuid", response.data)
        self.assertIn("user_uuid", response.data)

        # Verify project was actually created with correct data
        project = Project.objects.get(vtex_account="newstore")
        self.assertEqual(project.name, "New Store Project")
        self.assertEqual(project.language, "pt-br")
        self.assertEqual(str(project.uuid), response.data["project_uuid"])

    @patch("connect.billing.get_gateway")
    def test_idempotent_returns_existing_project(self, mock_gateway):
        """Calling twice with the same vtex_account should return the same
        project and update the language if it changed."""
        mock_gateway.return_value = StripeMockGateway()

        # Pre-create org + project with language "en-us"
        organization = Organization.objects.create(
            name="existing-store",
            description="Organization existing-store",
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        project = Project.objects.create(
            name="existing-store",
            organization=organization,
            vtex_account="existing-store",
            flow_organization=uuid.uuid4(),
            project_type=TypeProject.COMMERCE,
            language="en-us",
        )
        OrganizationAuthorization.objects.create(
            user=self.user,
            organization=organization,
            role=OrganizationRole.ADMIN.value,
        )

        # Call the endpoint with language "pt-br" for the same vtex_account
        response = self.client.post(
            self.url,
            {
                "user_email": self.user.email,
                "vtex_account": "existing-store",
                "language": "pt-br",
                "organization_name": "Existing Store Org",
                "project_name": "Existing Store Project",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["project_uuid"], str(project.uuid))

        # Verify language was updated from "en-us" to "pt-br"
        project.refresh_from_db()
        self.assertEqual(project.language, "pt-br")

    @patch("connect.billing.get_gateway")
    def test_existing_project_ensures_permissions(self, mock_gateway):
        """When the project already exists but the user has no permissions,
        the endpoint should create org authorization (ADMIN) and
        project authorization for the user."""
        mock_gateway.return_value = StripeMockGateway()

        # Pre-create org + project without any authorization for self.user
        organization = Organization.objects.create(
            name="permstore",
            description="Organization permstore",
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        project = Project.objects.create(
            name="permstore",
            organization=organization,
            vtex_account="permstore",
            flow_organization=uuid.uuid4(),
            project_type=TypeProject.COMMERCE,
        )

        response = self.client.post(
            self.url,
            {
                "user_email": self.user.email,
                "vtex_account": "permstore",
                "language": "es",
                "organization_name": "Perm Store Org",
                "project_name": "Perm Store Project",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify permissions were created
        self.assertTrue(
            OrganizationAuthorization.objects.filter(
                user=self.user, organization=organization
            ).exists()
        )
        self.assertTrue(
            ProjectAuthorization.objects.filter(
                user=self.user, project=project
            ).exists()
        )

    def test_missing_required_fields_returns_400(self):
        """Sending an empty body should fail validation for all required fields."""
        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_language_returns_400(self):
        """Language must be one of the choices defined in settings.LANGUAGES."""
        response = self.client.post(
            self.url,
            {
                "user_email": "a@b.com",
                "vtex_account": "store",
                "language": "invalid-lang",
                "organization_name": "Org",
                "project_name": "Project",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_email_returns_400(self):
        """user_email must be a valid email format."""
        response = self.client.post(
            self.url,
            {
                "user_email": "not-an-email",
                "vtex_account": "store",
                "language": "pt-br",
                "organization_name": "Org",
                "project_name": "Project",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_request_returns_403(self):
        """A user without the 'can_communicate_internally' permission
        should be rejected with 403 Forbidden."""
        unauth_client = APIClient()
        other_user, _ = create_user_and_token("noperm")
        unauth_client.force_authenticate(user=other_user)

        response = unauth_client.post(
            self.url,
            {
                "user_email": "user@vtex.com",
                "vtex_account": "store",
                "language": "pt-br",
                "organization_name": "Org",
                "project_name": "Project",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


@override_settings(USE_EDA_PERMISSIONS=False)
class CreateVtexProjectUseCaseTestCase(APITestCase):
    """Unit-level tests for the use case, exercising EDA publisher interactions."""

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

        self.user, _ = create_user_and_token("ucuser")
        # Mock EDA publisher to verify event publishing without RabbitMQ
        self.mock_eda = Mock()

    @patch("connect.billing.get_gateway")
    def test_publisher_called_on_creation(self, mock_gateway):
        """When a new project is created, both EDA events should be published:
        one for org creation (orgs.topic) and one for project creation (projects.topic)."""
        mock_gateway.return_value = StripeMockGateway()

        dto = CreateVtexProjectDTO(
            user_email=self.user.email,
            vtex_account="pub-store",
            language="pt-br",
            organization_name="Pub Store Org",
            project_name="Pub Store Project",
        )
        use_case = CreateVtexProjectUseCase(eda_publisher=self.mock_eda)
        result = use_case.execute(dto)

        self.assertIn("project_uuid", result)

        # Verify both EDA events were published
        self.mock_eda.publish_org_created.assert_called_once()
        self.mock_eda.publish_project_created.assert_called_once()

        # Verify the project event carries the correct language and vtex_account
        project_call_args = self.mock_eda.publish_project_created.call_args
        project = project_call_args[1].get("project") or project_call_args[0][0]
        self.assertEqual(project.language, "pt-br")
        self.assertEqual(project.vtex_account, "pub-store")

    @patch("connect.billing.get_gateway")
    def test_new_user_created_via_keycloak(self, mock_gateway):
        """When user_email does not exist in DB, the use case should create
        the user via Keycloak and send the access password email."""
        mock_gateway.return_value = StripeMockGateway()
        new_email = "brand_new@vtex.com"
        new_user = User.objects.create(email=new_email, username="brand_new_vtex")

        with patch(
            "connect.usecases.commerce.create_vtex_project.CreateKeycloakUserUseCase"
        ) as mock_kc, patch(
            "connect.usecases.commerce.create_vtex_project.User.objects.get",
            side_effect=User.DoesNotExist,
        ):
            mock_kc_instance = mock_kc.return_value
            mock_kc_instance.execute.return_value = {
                "user": new_user,
                "password": "TempPass1!",
            }
            new_user.send_email_access_password = Mock()

            dto = CreateVtexProjectDTO(
                user_email=new_email,
                vtex_account="keycloak-store",
                language="pt-br",
                organization_name="KC Store Org",
                project_name="KC Store Project",
            )
            use_case = CreateVtexProjectUseCase(eda_publisher=self.mock_eda)
            result = use_case.execute(dto)

        self.assertEqual(result["user_uuid"], str(new_user.pk))
        mock_kc.assert_called_once()
        new_user.send_email_access_password.assert_called_once_with("TempPass1!")

    @patch("connect.billing.get_gateway")
    def test_publisher_not_called_on_existing_project(self, mock_gateway):
        """When the project already exists (idempotent call), no EDA events
        should be published — avoids duplicate events on Retail side."""
        mock_gateway.return_value = StripeMockGateway()

        # Pre-create org + project to simulate an already-existing vtex_account
        organization = Organization.objects.create(
            name="existing",
            description="Organization existing",
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        Project.objects.create(
            name="existing",
            organization=organization,
            vtex_account="existing",
            flow_organization=uuid.uuid4(),
            project_type=TypeProject.COMMERCE,
        )

        dto = CreateVtexProjectDTO(
            user_email=self.user.email,
            vtex_account="existing",
            language="pt-br",
            organization_name="Existing Org",
            project_name="Existing Project",
        )
        use_case = CreateVtexProjectUseCase(eda_publisher=self.mock_eda)
        use_case.execute(dto)

        # No events should be fired for an existing project
        self.mock_eda.publish_org_created.assert_not_called()
        self.mock_eda.publish_project_created.assert_not_called()

    @patch("connect.billing.get_gateway")
    def test_permissions_created_via_request_permission(self, mock_gateway):
        """When user has no permissions on an existing project, _ensure_permissions
        should create a RequestPermissionOrganization which triggers the signal
        to create OrgAuth + ProjectAuth — replicating the legacy check-project flow."""
        mock_gateway.return_value = StripeMockGateway()

        organization = Organization.objects.create(
            name="perm-test-org",
            description="Organization perm-test-org",
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        project = Project.objects.create(
            name="perm-test-project",
            organization=organization,
            vtex_account="perm-test-store",
            flow_organization=uuid.uuid4(),
            project_type=TypeProject.COMMERCE,
        )

        dto = CreateVtexProjectDTO(
            user_email=self.user.email,
            vtex_account="perm-test-store",
            language="pt-br",
            organization_name="Perm Test Org",
            project_name="Perm Test Project",
        )
        use_case = CreateVtexProjectUseCase(eda_publisher=self.mock_eda)
        result = use_case.execute(dto)

        self.assertEqual(result["project_uuid"], str(project.uuid))

        # Signal should have created OrgAuth (ADMIN) and ProjectAuth
        self.assertTrue(
            OrganizationAuthorization.objects.filter(
                user=self.user,
                organization=organization,
                role=OrganizationRole.ADMIN.value,
            ).exists()
        )
        self.assertTrue(
            ProjectAuthorization.objects.filter(
                user=self.user, project=project
            ).exists()
        )

        # RequestPermissionOrganization should have been deleted by the signal
        self.assertFalse(
            RequestPermissionOrganization.objects.filter(
                email=self.user.email, organization=organization
            ).exists()
        )

    @patch("connect.billing.get_gateway")
    def test_multiple_projects_same_vtex_account_raises_error(self, mock_gateway):
        """When multiple projects share the same vtex_account, the use case
        should raise ValueError — we enforce one project per vtex_account."""
        mock_gateway.return_value = StripeMockGateway()

        organization = Organization.objects.create(
            name="dup-org",
            description="Organization dup-org",
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        # Create two projects with the same vtex_account
        Project.objects.create(
            name="dup-project-1",
            organization=organization,
            vtex_account="dup-store",
            flow_organization=uuid.uuid4(),
            project_type=TypeProject.COMMERCE,
        )
        Project.objects.create(
            name="dup-project-2",
            organization=organization,
            vtex_account="dup-store",
            flow_organization=uuid.uuid4(),
            project_type=TypeProject.COMMERCE,
        )

        dto = CreateVtexProjectDTO(
            user_email=self.user.email,
            vtex_account="dup-store",
            language="pt-br",
            organization_name="Dup Org",
            project_name="Dup Project",
        )
        use_case = CreateVtexProjectUseCase(eda_publisher=self.mock_eda)

        with self.assertRaises(ValueError) as ctx:
            use_case.execute(dto)

        self.assertIn("Multiple projects", str(ctx.exception))


@override_settings(USE_EDA_PERMISSIONS=False)
class SetVtexHostStoreViewTestCase(APITestCase):
    """Tests for PATCH /v2/commerce/projects/<uuid>/set-vtex-host-store/"""

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
        self.user, self.token = create_user_and_token("hostuser")

        content_type = ContentType.objects.get_for_model(User)
        permission, _ = Permission.objects.get_or_create(
            codename="can_communicate_internally",
            name="can communicate internally",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)
        self.client.force_authenticate(user=self.user)

        self.organization = Organization.objects.create(
            name="host-org",
            description="Organization host-org",
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        self.project = Project.objects.create(
            name="host-project",
            organization=self.organization,
            vtex_account="host-store",
            flow_organization=uuid.uuid4(),
            project_type=TypeProject.COMMERCE,
        )

    def _url(self, project_uuid=None):
        uid = project_uuid or str(self.project.uuid)
        return reverse("set-vtex-host-store", kwargs={"project_uuid": uid})

    @patch(
        "connect.usecases.commerce.set_vtex_host_store.UpdateProjectUseCase"
    )
    def test_set_vtex_host_store_successfully(self, mock_update_uc):
        """Sets vtex_host_store in project config and returns 200."""
        mock_update_uc.return_value = Mock()

        response = self.client.patch(
            self._url(),
            {"vtex_host_store": "https://www.mystore.com.br/"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["vtex_host_store"], "https://www.mystore.com.br/"
        )

        self.project.refresh_from_db()
        self.assertEqual(
            self.project.config["vtex_host_store"],
            "https://www.mystore.com.br/",
        )

    @patch(
        "connect.usecases.commerce.set_vtex_host_store.UpdateProjectUseCase"
    )
    def test_preserves_existing_config_keys(self, mock_update_uc):
        """Setting vtex_host_store should not overwrite other config keys."""
        mock_update_uc.return_value = Mock()

        self.project.config = {"store_type": "vtex-io"}
        self.project.save(update_fields=["config"])

        response = self.client.patch(
            self._url(),
            {"vtex_host_store": "https://www.mystore.com.br/"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.project.refresh_from_db()
        self.assertEqual(self.project.config["store_type"], "vtex-io")
        self.assertEqual(
            self.project.config["vtex_host_store"],
            "https://www.mystore.com.br/",
        )

    @patch(
        "connect.usecases.commerce.set_vtex_host_store.UpdateProjectUseCase"
    )
    def test_publishes_eda_event(self, mock_update_uc):
        """After saving config, the use case should publish an EDA update event."""
        mock_instance = Mock()
        mock_update_uc.return_value = mock_instance

        self.client.patch(
            self._url(),
            {"vtex_host_store": "https://www.mystore.com.br/"},
            format="json",
        )

        mock_instance.send_updated_project.assert_called_once()

    def test_project_not_found_returns_404(self):
        """Using a non-existent project UUID should return 404."""
        fake_uuid = str(uuid.uuid4())
        response = self.client.patch(
            self._url(fake_uuid),
            {"vtex_host_store": "https://www.mystore.com.br/"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_missing_vtex_host_store_returns_400(self):
        """Sending an empty body should fail validation."""
        response = self.client.patch(self._url(), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_url_returns_400(self):
        """vtex_host_store must be a valid URL."""
        response = self.client.patch(
            self._url(),
            {"vtex_host_store": "not-a-url"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_request_returns_403(self):
        """A user without internal permission should be rejected."""
        unauth_client = APIClient()
        other_user, _ = create_user_and_token("noperm-host")
        unauth_client.force_authenticate(user=other_user)

        response = unauth_client.patch(
            self._url(),
            {"vtex_host_store": "https://www.mystore.com.br/"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


@override_settings(USE_EDA_PERMISSIONS=False)
class SetVtexHostStoreUseCaseTestCase(APITestCase):
    """Unit tests for SetVtexHostStoreUseCase."""

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

        self.organization = Organization.objects.create(
            name="uc-org",
            description="Organization uc-org",
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        self.project = Project.objects.create(
            name="uc-project",
            organization=self.organization,
            vtex_account="uc-store",
            flow_organization=uuid.uuid4(),
            project_type=TypeProject.COMMERCE,
        )

    def test_execute_sets_config_and_publishes(self):
        """execute() should persist vtex_host_store in config and call EDA publisher."""
        mock_update = Mock()
        use_case = SetVtexHostStoreUseCase(update_project_usecase=mock_update)

        result = use_case.execute(
            str(self.project.uuid), "https://www.example.com/"
        )

        self.project.refresh_from_db()
        self.assertEqual(
            self.project.config["vtex_host_store"],
            "https://www.example.com/",
        )
        self.assertEqual(result["vtex_host_store"], "https://www.example.com/")
        mock_update.send_updated_project.assert_called_once_with(
            self.project, user_email=""
        )

    def test_execute_raises_for_nonexistent_project(self):
        """execute() should raise Project.DoesNotExist for unknown UUID."""
        mock_update = Mock()
        use_case = SetVtexHostStoreUseCase(update_project_usecase=mock_update)

        with self.assertRaises(Project.DoesNotExist):
            use_case.execute(str(uuid.uuid4()), "https://www.example.com/")
