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
    BillingPlan,
    Organization,
    OrganizationAuthorization,
    OrganizationRole,
    Project,
    TypeProject,
)
from connect.common.mocks import StripeMockGateway
from connect.usecases.organizations.list_by_user import ListOrgsByUserUseCase


@override_settings(USE_EDA_PERMISSIONS=False)
class OrgsByUserBaseTestCase(APITestCase):
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

        self.member, _ = create_user_and_token("orgmember")
        self.other, _ = create_user_and_token("orgother")

        self.organization = Organization.objects.create(
            name="member-org",
            description="Organization member-org",
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        OrganizationAuthorization.objects.create(
            user=self.member,
            organization=self.organization,
            role=OrganizationRole.ADMIN.value,
        )
        OrganizationAuthorization.objects.create(
            user=self.other,
            organization=self.organization,
            role=OrganizationRole.CONTRIBUTOR.value,
        )
        self.project = Project.objects.create(
            name="member-project",
            organization=self.organization,
            flow_organization=uuid.uuid4(),
            project_type=TypeProject.COMMERCE,
        )


class ListOrgsByUserUseCaseTestCase(OrgsByUserBaseTestCase):
    def test_returns_orgs_with_projects_and_member_count(self):
        result = ListOrgsByUserUseCase().execute(self.member.email)

        self.assertEqual(len(result), 1)
        org = result[0]
        self.assertEqual(org["uuid"], str(self.organization.uuid))
        self.assertEqual(org["name"], "member-org")
        self.assertEqual(org["member_count"], 2)
        self.assertEqual(
            org["projects"],
            [{"uuid": str(self.project.uuid), "name": "member-project"}],
        )

    def test_excludes_not_setted_role_from_member_count(self):
        ghost, _ = create_user_and_token("ghost")
        OrganizationAuthorization.objects.create(
            user=ghost,
            organization=self.organization,
            role=OrganizationRole.NOT_SETTED.value,
        )

        result = ListOrgsByUserUseCase().execute(self.member.email)

        self.assertEqual(result[0]["member_count"], 2)

    def test_returns_empty_for_unknown_user(self):
        result = ListOrgsByUserUseCase().execute("missing@user.com")
        self.assertEqual(result, [])

    @patch("connect.billing.get_gateway")
    def test_returns_empty_when_only_not_setted_role(self, mock_gateway):
        mock_gateway.return_value = StripeMockGateway()
        loner, _ = create_user_and_token("loner")
        org = Organization.objects.create(
            name="loner-org",
            description="Organization loner-org",
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        OrganizationAuthorization.objects.create(
            user=loner,
            organization=org,
            role=OrganizationRole.NOT_SETTED.value,
        )

        result = ListOrgsByUserUseCase().execute(loner.email)
        self.assertEqual(result, [])


class OrgsByUserViewTestCase(OrgsByUserBaseTestCase):
    def setUp(self):
        super().setUp()
        self.client = APIClient()

        content_type = ContentType.objects.get_for_model(User)
        permission, _ = Permission.objects.get_or_create(
            codename="can_communicate_internally",
            name="can communicate internally",
            content_type=content_type,
        )
        self.member.user_permissions.add(permission)
        self.client.force_authenticate(user=self.member)
        self.url = reverse("orgs-by-user")

    def test_returns_200_with_organizations(self):
        response = self.client.get(self.url, {"user_email": self.member.email})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["organizations"]), 1)
        self.assertEqual(
            response.data["organizations"][0]["uuid"],
            str(self.organization.uuid),
        )

    def test_missing_user_email_returns_400(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_request_returns_403(self):
        unauth_client = APIClient()
        no_perm, _ = create_user_and_token("orgnoperm")
        unauth_client.force_authenticate(user=no_perm)

        response = unauth_client.get(self.url, {"user_email": self.member.email})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
