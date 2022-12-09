import json
from django.test import RequestFactory
from django.test import TestCase
from rest_framework import status

from connect.api.v1.organization.views import (
    OrganizationViewSet,
)
from connect.api.v1.account.views import (
    MyUserProfileViewSet,
)
from connect.api.v1.tests.utils import create_user_and_token
from connect.common.models import (
    Organization,
    BillingPlan,
    OrganizationRole,
)


class TwoFactorAuthTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.owner, self.owner_token = create_user_and_token("owner")
        self.user, self.user_token = create_user_and_token("user")
        self.organization = Organization.objects.create(
            name="test organization",
            description="test organization",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="free",
        )
        self.organization_authorization = self.organization.authorizations.create(
            user=self.owner, role=OrganizationRole.ADMIN.value
        )
        self.user_organization_authorization = self.organization.authorizations.create(
            user=self.user, role=OrganizationRole.ADMIN.value
        )

    def request_enforce_2fa(self, organization_uuid, data, token=None):
        authorization_header = (
            {"HTTP_AUTHORIZATION": "Token {}".format(token.key)} if token else {}
        )
        request = self.factory.patch(
            f"/v1/organization/org/enforce-two-factor-auth/{organization_uuid}/",
            data=json.dumps(data),
            content_type="application/json",
            format="json",
            **authorization_header,
        )
        response = OrganizationViewSet.as_view({"patch": "set_2fa_required"})(
            request,
            organization_uuid=self.organization.uuid,
        )

        content_data = json.loads(response.content)
        return response, content_data

    def request_get_org(self, organization_uuid, token=None):
        authorization_header = (
            {"HTTP_AUTHORIZATION": "Token {}".format(token.key)} if token else {}
        )
        request = self.factory.get(
            f"v1/organization/project/?organization={organization_uuid}",
            **authorization_header,
        )
        response = OrganizationViewSet.as_view({"get": "list"})(request)
        response.render()
        content_data = json.loads(response.content)
        return (response, content_data)

    def request_user_2fa(self, data, token=None):
        authorization_header = (
            {"HTTP_AUTHORIZATION": "Token {}".format(token.key)} if token else {}
        )
        request = self.factory.patch(
            "/v1/account/my-profile/set_two_factor_authentication/",
            data=json.dumps(data),
            content_type="application/json",
            format="json",
            **authorization_header,
        )
        response = MyUserProfileViewSet.as_view(
            {"patch": "set_two_factor_authentication"}
        )(
            request,
        )
        return response

    def test_ok(self):
        data = {"2fa_required": True}
        # enforces 2fa for organization
        _, content_data = self.request_enforce_2fa(
            self.organization.uuid, data, self.owner_token
        )

        self.assertTrue(content_data["2fa_required"])

        # user cant access cause he dosen't have 2fa
        response, content_data = self.request_get_org(
            self.organization.uuid, self.user_token
        )
        self.assertEquals(response.status_code, status.HTTP_403_FORBIDDEN)
