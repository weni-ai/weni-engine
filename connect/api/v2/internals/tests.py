import json
import uuid
from rest_framework import status
from rest_framework.test import APIRequestFactory
from rest_framework.exceptions import PermissionDenied

from django.test import TestCase
from unittest.mock import patch

from connect.authentication.models import User
from connect.api.v1.tests.utils import create_user_and_token
from connect.common.models import (
    Organization,
    BillingPlan,
    Project,
    OrganizationRole,
    OrganizationLevelRole,
    RequestPermissionOrganization,
)
from connect.common.mocks import StripeMockGateway
from connect.api.v2.internals.views import AIGetOrganizationView
from connect.api.v2.internals.serializers import (
    OrganizationAuthorizationRoleSerializer,
    RequestPermissionOrganizationSerializer,
)


class AIGetOrganizationViewTestCase(TestCase):
    @patch("connect.billing.get_gateway")
    @patch(
        "connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.update_user_permission_project"
    )
    @patch(
        "connect.api.v1.internal.integrations.integrations_rest_client.IntegrationsRESTClient.update_user_permission_project"
    )
    def setUp(self, integrations_rest, flows_rest, mock_get_gateway):
        mock_get_gateway.return_value = StripeMockGateway()
        integrations_rest.side_effect = [200, 200]
        flows_rest.side_effect = [200, 200]

        self.factory = APIRequestFactory()
        self.user, self.user_token = create_user_and_token("user")
        self.user_2, self.user2_token = create_user_and_token("user_2")

        self.org_1 = Organization.objects.create(
            name="V2 Org 1",
            description="V2 Org 1",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )

        self.project1 = Project.objects.create(
            name="V2 Project 1", flow_organization=uuid.uuid4(), organization=self.org_1
        )
        self.org_auth_1 = self.org_1.authorizations.create(
            user=self.user, role=OrganizationRole.ADMIN.value
        )
        self.org_auth_1 = self.org_1.authorizations.create(
            user=self.user_2, role=OrganizationRole.ADMIN.value
        )

    def request(self, **kwargs):

        project_uuid = kwargs.get("project_uuid")
        query_params = {"project_uuid": project_uuid}

        path = f"/v2/internals/connect/organizations/?project_uuid={project_uuid}"

        request = self.factory.get(path)

        response = AIGetOrganizationView.as_view()(request, query_params=query_params)
        response.render()
        content_data = json.loads(response.content)

        return response, content_data

    @patch("connect.api.v1.internal.permissions.ModuleHasPermission.has_permission")
    def test_retrieve_organization(self, module_has_permission):
        module_has_permission.side_effect = [True, True]

        project_uuid = str(self.project1.uuid)

        response, content_data = self.request(project_uuid=project_uuid)
        self.assertEquals(response.status_code, status.HTTP_200_OK)

    @patch("connect.api.v1.internal.permissions.ModuleHasPermission.has_permission")
    def test_fail_retrieve_organization(self, module_has_permission):
        module_has_permission.side_effect = [True, True]

        project_uuid = str(uuid.uuid4())

        response, content_data = self.request(project_uuid=project_uuid)
        self.assertEquals(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch("connect.api.v1.internal.permissions.ModuleHasPermission.has_permission")
    def test_update_organization(self, module_has_permission):
        module_has_permission.side_effect = [True, True]
        project_uuid = str(self.project1.uuid)
        query_params = {"project_uuid": project_uuid}

        path = f"/v2/internals/connect/organizations/?project_uuid={project_uuid}"

        data = {"intelligence_organization": 1}

        request = self.factory.patch(
            path,
            data=json.dumps(data),
            format="json",
        )

        response = AIGetOrganizationView.as_view()(
            request, query_params=query_params, data=data
        )
        response.render()
        content_data = json.loads(response.content)

        organization = Organization.objects.get(
            uuid=content_data.get("organization").get("uuid")
        )

        self.assertEquals(response.status_code, status.HTTP_200_OK)
        self.assertEquals(
            organization.inteligence_organization, data.get("intelligence_organization")
        )


class RequestPermissionOrganizationSerializerTestCase(TestCase):
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway):
        mock_get_gateway.return_value = StripeMockGateway()
        self.test_serializer = RequestPermissionOrganizationSerializer()

        self.org_test = Organization.objects.create(
            name="test organization",
            description="",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="enterprise",
        )

        self.test_user = User.objects.create(
            email="test@test.com",
            username="test",
            first_name="first_name",
            last_name="last_name",
        )

    def test_validate_role_nothing(self):
        attrs = {
            "email": "test@example.com",
            "role": OrganizationLevelRole.NOTHING.value,
        }

        with self.assertRaises(PermissionDenied) as context:
            self.test_serializer.validate(attrs)

        self.assertEqual(str(context.exception), "You cannot set user role 0")

    def test_validate_role_valid(self):
        attrs = {
            "email": "test@example.com",
            "role": OrganizationLevelRole.ADMIN.value,
        }

        try:
            validated_attrs = self.test_serializer.validate(attrs)
        except PermissionDenied:
            self.fail("Unexpected PermissionDenied exception.")

        self.assertEqual(attrs, validated_attrs)

    def test_get_existing_user_data(self):

        request_permission = RequestPermissionOrganization.objects.create(
            email="test@test.com",
            role=OrganizationRole.ADMIN.value,
            organization=self.org_test,
            created_by=self.test_user,
        )

        data = self.test_serializer.get_user_data(request_permission)
        self.assertEqual(
            f"{self.test_user.first_name} {self.test_user.last_name}", data["name"]
        )

    def test_get_non_existing_user_data(self):

        non_existing_email = "test2@test.com"

        request_permission = RequestPermissionOrganization.objects.create(
            email=non_existing_email,
            role=OrganizationRole.ADMIN.value,
            organization=self.org_test,
            created_by=self.test_user,
        )

        data = self.test_serializer.get_user_data(request_permission)
        self.assertEqual(data["name"], non_existing_email)


class OrganizationAuthorizationRoleSerializerTestCase(TestCase):
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway):
        mock_get_gateway.return_value = StripeMockGateway()
        self.test_serializer = OrganizationAuthorizationRoleSerializer()

        self.org_test = Organization.objects.create(
            name="test organization",
            description="",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="enterprise",
        )

        self.test_user = User.objects.create(
            email="test@test.com",
            username="test",
            first_name="first_name",
            last_name="last_name",
        )

    def test_validate_role_nothing(self):
        attrs = {
            "email": "test@example.com",
            "role": OrganizationLevelRole.NOTHING.value,
        }

        with self.assertRaises(PermissionDenied) as context:
            self.test_serializer.validate(attrs)

        self.assertEqual(str(context.exception), "You cannot set user role 0")

    def test_validate_role_valid(self):
        attrs = {
            "email": "test@example.com",
            "role": OrganizationLevelRole.ADMIN.value,
        }

        try:
            validated_attrs = self.test_serializer.validate(attrs)
        except PermissionDenied:
            self.fail("Unexpected PermissionDenied exception.")

        self.assertEqual(attrs, validated_attrs)
