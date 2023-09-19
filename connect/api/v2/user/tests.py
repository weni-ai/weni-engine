
import uuid as uuid4
from unittest.mock import Mock, patch
from rest_framework import status
from rest_framework.test import APIRequestFactory
from django.test import TestCase, RequestFactory, override_settings
from .views import UserAPIToken, UserIsPaying
from connect.common.mocks import StripeMockGateway
from connect.api.v1.tests.utils import create_user_and_token
from connect.common.models import Project, Organization, OrganizationRole, BillingPlan


class UserAPITokenTestCase(TestCase):

    @patch("connect.common.signals.update_user_permission_project")
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway, mock_permission):
        self.factory = RequestFactory()
        self.owner, self.owner_token = create_user_and_token("owner")
        mock_get_gateway.return_value = StripeMockGateway()
        mock_permission.return_value = True
        self.organization = Organization.objects.create(
            name="test organization",
            description="",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="free",
        )
        self.organization_authorization = self.organization.authorizations.create(
            user=self.owner, role=OrganizationRole.ADMIN.value
        )

        self.project1 = Project.objects.create(
            name="project 1",
            flow_organization=uuid4.uuid4(),
            organization=self.organization,
            contact_count=25,
        )
        self.view = UserAPIToken.as_view()

    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.get_user_api_token")
    def test_get_user_api_token(self, mock_get_user_api_token):

        response_data = {"api_token": "mocked_token"}
        mock_response = Mock(
            status_code=status.HTTP_200_OK,
            json=Mock(return_value=response_data)
        )
        mock_get_user_api_token.return_value = mock_response

        request = self.factory.get(
            f"/projects/{self.project1.uuid}/user-api-token/",
            data={
                "project_uuid": self.project1.uuid,
                "user": self.owner.email
            }
        )
        response = self.view(request, project_uuid=self.project1.uuid)

        self.assertEqual(response.status_code, status.HTTP_200_OK)


class UserIsPayingTestCase(TestCase):

    @patch("connect.common.signals.update_user_permission_project")
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway, mock_permission):
        self.owner, self.owner_token = create_user_and_token("owner")
        mock_get_gateway.return_value = StripeMockGateway()
        mock_permission.return_value = True
        self.organization = Organization.objects.create(
            name="test organization",
            description="",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="free",
        )

        self.project1 = Project.objects.create(
            name="project 1",
            flow_organization=uuid4.uuid4(),
            organization=self.organization,
            contact_count=25,
        )
        self.view = UserIsPaying.as_view()

    def request(self, token, user_email):
        self.factory = APIRequestFactory()
        url = f"/v2/account/user-is-paying?user_email={user_email}"
        request = self.factory.get(url, format="json")
        request.META["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        return request

    @override_settings(VERIFICATION_MARKETING_TOKEN="Bearer valid_marketing_token")
    def test_get_endpoint_valid_token_no_auth(self):
        token = "valid_marketing_token"
        response = self.view(self.request(token, self.owner.email))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_endpoint_invalid_token(self):
        invalid_token = "invalid_marketing_token"
        response = self.view(self.request(invalid_token, self.owner.email))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @override_settings(VERIFICATION_MARKETING_TOKEN="Bearer valid_marketing_token")
    def test_get_endpoint_valid_token(self):
        self.organization.authorizations.create(
            user=self.owner, role=OrganizationRole.ADMIN.value
        )
        token = "valid_marketing_token"
        response = self.view(self.request(token, self.owner.email))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
