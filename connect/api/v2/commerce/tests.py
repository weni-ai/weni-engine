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
from connect.usecases.commerce.dto import CreateVtexProjectDTO, SuspendVtexProjectDTO
from connect.usecases.commerce.set_vtex_host_store import SetVtexHostStoreUseCase
from connect.usecases.commerce.suspend_vtex_project import SuspendVtexProjectUseCase
from connect.usecases.commerce.update_project_config import UpdateProjectConfigUseCase


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


@override_settings(USE_EDA_PERMISSIONS=False)
class SuspendVtexProjectViewTestCase(APITestCase):
    """Tests for POST /v2/commerce/projects/<uuid>/suspend/"""

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
        self.user, self.token = create_user_and_token("suspenduser")

        content_type = ContentType.objects.get_for_model(User)
        permission, _ = Permission.objects.get_or_create(
            codename="can_communicate_internally",
            name="can communicate internally",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)
        self.client.force_authenticate(user=self.user)

        self.organization = Organization.objects.create(
            name="suspend-org",
            description="Organization suspend-org",
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        self.project = Project.objects.create(
            name="suspend-project",
            organization=self.organization,
            vtex_account="suspend-store",
            flow_organization=uuid.uuid4(),
            project_type=TypeProject.COMMERCE,
        )

    def _url(self, project_uuid=None):
        uid = project_uuid or str(self.project.uuid)
        return reverse("suspend-vtex-project", kwargs={"project_uuid": uid})

    @patch("connect.common.models.send_mass_html_mail")
    def test_suspend_project_successfully(self, mock_mail):
        """Suspending a trial project should set is_suspended=True and return 200."""
        mock_mail.return_value = None

        response = self.client.post(
            self._url(),
            {"conversation_limit": 1000},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["suspended"])

        self.organization.refresh_from_db()
        self.assertTrue(self.organization.is_suspended)

        billing = self.organization.organization_billing
        self.assertFalse(billing.is_active)

    @patch("connect.common.models.send_mass_html_mail")
    def test_idempotent_when_already_suspended(self, mock_mail):
        """Calling suspend on an already-suspended project returns 200
        with already_suspended=True and does not send duplicate emails."""
        mock_mail.return_value = None
        self.organization.is_suspended = True
        self.organization.save(update_fields=["is_suspended"])

        response = self.client.post(
            self._url(),
            {"conversation_limit": 1000},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["already_suspended"])
        mock_mail.assert_not_called()

    def test_project_not_found_returns_404(self):
        """Using a non-existent project UUID should return 404."""
        fake_uuid = str(uuid.uuid4())
        response = self.client.post(
            self._url(fake_uuid),
            {"conversation_limit": 1000},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_missing_conversation_limit_returns_400(self):
        """Sending an empty body should fail validation."""
        response = self.client.post(self._url(), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_conversation_limit_returns_400(self):
        """conversation_limit must be a positive integer."""
        response = self.client.post(
            self._url(),
            {"conversation_limit": 0},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_request_returns_403(self):
        """A user without internal permission should be rejected."""
        unauth_client = APIClient()
        other_user, _ = create_user_and_token("noperm-suspend")
        unauth_client.force_authenticate(user=other_user)

        response = unauth_client.post(
            self._url(),
            {"conversation_limit": 1000},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch("connect.billing.get_gateway")
    @patch("connect.common.models.send_mass_html_mail")
    def test_non_trial_plan_returns_400(self, mock_mail, mock_gateway):
        """Suspending a project that is not on a trial plan should return 400."""
        mock_gateway.return_value = StripeMockGateway()
        mock_mail.return_value = None

        billing = self.organization.organization_billing
        billing.plan = BillingPlan.PLAN_START
        billing.save(update_fields=["plan"])

        response = self.client.post(
            self._url(),
            {"conversation_limit": 1000},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("not on a trial plan", response.data["detail"])


@override_settings(USE_EDA_PERMISSIONS=False)
class SuspendVtexProjectUseCaseTestCase(APITestCase):
    """Unit tests for SuspendVtexProjectUseCase."""

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
            name="uc-suspend-org",
            description="Organization uc-suspend-org",
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        self.project = Project.objects.create(
            name="uc-suspend-project",
            organization=self.organization,
            vtex_account="uc-suspend-store",
            flow_organization=uuid.uuid4(),
            project_type=TypeProject.COMMERCE,
        )

    @patch("connect.common.models.send_mass_html_mail")
    def test_execute_suspends_organization(self, mock_mail):
        """execute() should suspend the organization and deactivate the billing plan."""
        mock_mail.return_value = None

        dto = SuspendVtexProjectDTO(
            project_uuid=str(self.project.uuid),
            conversation_limit=1000,
        )
        use_case = SuspendVtexProjectUseCase()
        result = use_case.execute(dto)

        self.assertTrue(result["suspended"])

        self.organization.refresh_from_db()
        self.assertTrue(self.organization.is_suspended)
        self.assertFalse(self.organization.organization_billing.is_active)

    @patch(
        "connect.common.models.BillingPlan.send_email_trial_plan_expired_due_conversation_limit"
    )
    @patch("connect.common.models.BillingPlan.end_trial_period")
    def test_execute_sends_conversation_limit_email(self, mock_end_trial, mock_email):
        """execute() should call the message-limit email method."""
        dto = SuspendVtexProjectDTO(
            project_uuid=str(self.project.uuid),
            conversation_limit=1000,
        )
        use_case = SuspendVtexProjectUseCase()
        use_case.execute(dto)

        mock_end_trial.assert_called_once()
        mock_email.assert_called_once_with(1000)

    @patch("connect.common.models.send_mass_html_mail")
    def test_execute_skips_when_already_suspended(self, mock_mail):
        """execute() should return early when organization is already suspended."""
        mock_mail.return_value = None

        self.organization.is_suspended = True
        self.organization.save(update_fields=["is_suspended"])

        dto = SuspendVtexProjectDTO(
            project_uuid=str(self.project.uuid),
            conversation_limit=1000,
        )
        use_case = SuspendVtexProjectUseCase()
        result = use_case.execute(dto)

        self.assertTrue(result["already_suspended"])

    def test_execute_raises_for_nonexistent_project(self):
        """execute() should raise Project.DoesNotExist for unknown UUID."""
        dto = SuspendVtexProjectDTO(
            project_uuid=str(uuid.uuid4()),
            conversation_limit=1000,
        )
        use_case = SuspendVtexProjectUseCase()

        with self.assertRaises(Project.DoesNotExist):
            use_case.execute(dto)

    @patch("connect.billing.get_gateway")
    def test_execute_raises_for_non_trial_plan(self, mock_gateway):
        """execute() should raise ValueError when the plan is not trial."""
        mock_gateway.return_value = StripeMockGateway()

        billing = self.organization.organization_billing
        billing.plan = BillingPlan.PLAN_START
        billing.save(update_fields=["plan"])

        dto = SuspendVtexProjectDTO(
            project_uuid=str(self.project.uuid),
            conversation_limit=1000,
        )
        use_case = SuspendVtexProjectUseCase()

        with self.assertRaises(ValueError) as ctx:
            use_case.execute(dto)

        self.assertIn("not on a trial plan", str(ctx.exception))


@override_settings(USE_EDA_PERMISSIONS=False)
class UpdateProjectConfigViewTestCase(APITestCase):
    """Tests for PATCH /v2/commerce/projects/<uuid>/config/"""

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
        self.user, self.token = create_user_and_token("configuser")

        content_type = ContentType.objects.get_for_model(User)
        permission, _ = Permission.objects.get_or_create(
            codename="can_communicate_internally",
            name="can communicate internally",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)
        self.client.force_authenticate(user=self.user)

        self.organization = Organization.objects.create(
            name="config-org",
            description="Organization config-org",
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        self.project = Project.objects.create(
            name="config-project",
            organization=self.organization,
            vtex_account="config-store",
            flow_organization=uuid.uuid4(),
            project_type=TypeProject.COMMERCE,
        )

    def _url(self, project_uuid=None):
        uid = project_uuid or str(self.project.uuid)
        return reverse("update-project-config", kwargs={"project_uuid": uid})

    @patch(
        "connect.usecases.commerce.update_project_config.UpdateProjectUseCase"
    )
    def test_update_config_successfully(self, mock_update_uc):
        """PATCH with valid config dict returns 200 and persists the values."""
        mock_update_uc.return_value = Mock()

        response = self.client.patch(
            self._url(),
            {"config": {"vtex_host_store": "https://www.mystore.com.br/"}},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["config"]["vtex_host_store"],
            "https://www.mystore.com.br/",
        )

        self.project.refresh_from_db()
        self.assertEqual(
            self.project.config["vtex_host_store"],
            "https://www.mystore.com.br/",
        )

    @patch(
        "connect.usecases.commerce.update_project_config.UpdateProjectUseCase"
    )
    def test_merges_with_existing_config(self, mock_update_uc):
        """New keys should be added without removing existing ones."""
        mock_update_uc.return_value = Mock()

        self.project.config = {"store_type": "vtex-io"}
        self.project.save(update_fields=["config"])

        response = self.client.patch(
            self._url(),
            {"config": {"vtex_host_store": "https://www.mystore.com.br/"}},
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
        "connect.usecases.commerce.update_project_config.UpdateProjectUseCase"
    )
    def test_overwrite_existing_key(self, mock_update_uc):
        """Sending an existing key with a new value should overwrite it."""
        mock_update_uc.return_value = Mock()

        self.project.config = {"store_type": "vtex-io"}
        self.project.save(update_fields=["config"])

        response = self.client.patch(
            self._url(),
            {"config": {"store_type": "vtex-cms"}},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.project.refresh_from_db()
        self.assertEqual(self.project.config["store_type"], "vtex-cms")

    def test_empty_config_returns_400(self):
        """Sending an empty config dict should fail validation."""
        response = self.client.patch(
            self._url(), {"config": {}}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_config_returns_400(self):
        """Sending an empty body should fail validation."""
        response = self.client.patch(self._url(), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_project_not_found_returns_404(self):
        """Using a non-existent project UUID should return 404."""
        fake_uuid = str(uuid.uuid4())
        response = self.client.patch(
            self._url(fake_uuid),
            {"config": {"key": "value"}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


@override_settings(USE_EDA_PERMISSIONS=False)
class UpdateProjectConfigUseCaseTestCase(APITestCase):
    """Unit tests for UpdateProjectConfigUseCase."""

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
            name="uc-config-org",
            description="Organization uc-config-org",
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        self.project = Project.objects.create(
            name="uc-config-project",
            organization=self.organization,
            vtex_account="uc-config-store",
            flow_organization=uuid.uuid4(),
            project_type=TypeProject.COMMERCE,
        )

    def test_execute_merges_config_and_publishes(self):
        """execute() should merge config keys and call EDA publisher."""
        mock_update = Mock()
        use_case = UpdateProjectConfigUseCase(update_project_usecase=mock_update)

        self.project.config = {"existing_key": "existing_value"}
        self.project.save(update_fields=["config"])

        result = use_case.execute(
            str(self.project.uuid),
            {"new_key": "new_value"},
        )

        self.project.refresh_from_db()
        self.assertEqual(self.project.config["existing_key"], "existing_value")
        self.assertEqual(self.project.config["new_key"], "new_value")
        self.assertEqual(result["config"]["existing_key"], "existing_value")
        self.assertEqual(result["config"]["new_key"], "new_value")
        mock_update.send_updated_project.assert_called_once_with(
            self.project, user_email=""
        )

    def test_project_not_found_raises(self):
        """execute() should raise Project.DoesNotExist for unknown UUID."""
        mock_update = Mock()
        use_case = UpdateProjectConfigUseCase(update_project_usecase=mock_update)

        with self.assertRaises(Project.DoesNotExist):
            use_case.execute(str(uuid.uuid4()), {"key": "value"})
