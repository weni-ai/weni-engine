import json
from django.test import TestCase, RequestFactory

from connect.common.models import (
    BillingPlan,
    Organization,
    OrganizationRole,
    NewsletterOrganization,
)
from connect.api.v1.organization.views import OrganizationViewSet
from connect.api.v1.tests.utils import create_user_and_token

from rest_framework import status
from connect.common.mocks import StripeMockGateway
from unittest.mock import patch


class TrialNewsletterTestCase(TestCase):
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway) -> None:
        mock_get_gateway.return_value = StripeMockGateway()
        self.factory = RequestFactory()
        self.owner, self.owner_token = create_user_and_token("owner")
        self.organization = Organization.objects.create(
            name="test organization",
            description="test organization",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        self.organization_authorization = self.organization.authorizations.create(
            user=self.owner, role=OrganizationRole.ADMIN.value
        )

    @patch("connect.billing.get_gateway")
    def test_ok(self, mock_get_gateway):
        mock_get_gateway.return_value = StripeMockGateway()
        b = self.organization.organization_billing

        self.assertEquals(b.plan, BillingPlan.PLAN_TRIAL)
        self.assertTrue(b.is_active)

        b.end_trial_period()

        self.assertFalse(b.is_active)

        response, _ = self.change_plan()

        self.assertEquals(response.status_code, status.HTTP_200_OK)

        organization = Organization.objects.get(uuid=self.organization.uuid)

        organization_newsletters = NewsletterOrganization.objects.filter(
            organization=self.organization
        )
        self.assertIsNotNone(organization_newsletters)

        self.assertTrue(organization.organization_billing.is_active)
        self.assertFalse(organization.is_suspended)
        self.assertEquals(
            organization.organization_billing.plan, BillingPlan.PLAN_START
        )

        organization_newsletters = NewsletterOrganization.objects.filter(
            organization=self.organization
        )

        self.assertListEqual(list(organization_newsletters), [])

    def change_plan(self):
        url = f"/v1/organization/org/billing/change-plan/{self.organization.organization_billing.plan}/"

        authorization_header = (
            {"HTTP_AUTHORIZATION": "Token {}".format(self.owner_token.key)}
            if self.owner_token
            else {}
        )
        data = {"organization_billing_plan": BillingPlan.PLAN_START}
        request = self.factory.patch(
            url,
            data=json.dumps(data),
            content_type="application/json",
            format="json",
            **authorization_header,
        )
        response = OrganizationViewSet.as_view({"patch": "change_plan"})(
            request,
            organization_uuid=self.organization.uuid,
        )

        content_data = json.loads(response.content)
        return response, content_data
