import uuid

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from connect.api.v1.tests.utils import create_user_and_token
from connect.api.v2.channels.views import ListChannelsAPIView
from connect.common.models import (
    Organization,
    BillingPlan,
    OrganizationRole,
    Project,
    ProjectRole,
)


class ListChannelsAPIViewPermissionsTestCase(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

        self.user, _ = create_user_and_token("user")
        self.user_noauth, _ = create_user_and_token("user_noauth")

        self.org = Organization.objects.create(
            name="Org",
            description="Org",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )

        # Give user organization+project permission
        self.org_auth = self.org.authorizations.create(
            user=self.user, role=OrganizationRole.CONTRIBUTOR.value
        )

        self.project = Project.objects.create(
            name="Proj",
            flow_organization=uuid.uuid4(),
            organization=self.org,
        )
        # Ensure a single project authorization exists and has contributor role
        project_auth = self.project.get_user_authorization(self.user)
        project_auth.role = ProjectRole.CONTRIBUTOR.value
        project_auth.save(update_fields=["role"])

        self.view = ListChannelsAPIView.as_view()
        self.url = "/v2/projects/channels?channel_type=WA"

    def _grant_module_permission(self, user):
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        from django.contrib.auth import get_user_model

        User = get_user_model()
        content_type = ContentType.objects.get_for_model(User)
        perm, _ = Permission.objects.get_or_create(
            codename="can_communicate_internally",
            name="can communicate internally",
            content_type=content_type,
        )
        user.user_permissions.add(perm)

    def test_module_can_list_all_projects_channels(self):
        self._grant_module_permission(self.user)
        request = self.factory.get(self.url)
        force_authenticate(request, user=self.user, token=self.user.auth_token)

        # FlowsRESTClient.list_channel will be hit; keep it simple by mocking minimal response
        from unittest.mock import patch

        sample_resp = [
            {"uuid": str(uuid.uuid4()), "name": "ch1", "config": {}, "address": "a", "org": str(self.project.flow_organization), "is_active": True},
        ]
        with patch(
            "connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.list_channel",
            return_value=sample_resp,
        ):
            response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_with_project_permission_must_pass_project_uuid_and_succeeds(self):
        url = f"/v2/projects/channels?channel_type=WA&project_uuid={self.project.uuid}"
        request = self.factory.get(url)
        force_authenticate(request, user=self.user, token=self.user.auth_token)

        from unittest.mock import patch

        sample_resp = [
            {"uuid": str(uuid.uuid4()), "name": "ch1", "config": {}, "address": "a", "org": str(self.project.flow_organization), "is_active": True},
        ]
        with patch(
            "connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.list_channel",
            return_value=sample_resp,
        ):
            response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_without_project_permission_forbidden(self):
        url = f"/v2/projects/channels?channel_type=WA&project_uuid={self.project.uuid}"
        request = self.factory.get(url)
        force_authenticate(request, user=self.user_noauth, token=self.user_noauth.auth_token)

        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_without_project_uuid_validation_error(self):
        request = self.factory.get(self.url)
        force_authenticate(request, user=self.user, token=self.user.auth_token)

        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_user_unauthorized(self):
        request = self.factory.get(self.url)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
