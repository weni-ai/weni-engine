import json

from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.response import Response

from django.test import TestCase
from unittest.mock import patch

from connect.api.v1.tests.utils import create_user_and_token
from connect.common.models import Organization, BillingPlan, OrganizationRole
from connect.api.v2.organizations.views import OrganizationViewSet


class OrganizationViewSetTestCase(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user, self.user_token = create_user_and_token("user")
        self.user_403, self.user_403_token = create_user_and_token("user_403")

        self.org_1 = Organization.objects.create(
            name="V2 Org 1",
            description="V2 Org 1",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )

        self.org_2 = Organization.objects.create(
            name="V2 Org 2",
            description="V2 Org 2",
            inteligence_organization=2,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_ADVANCED,
        )

        self.org_3 = Organization.objects.create(
            name="V2 Org 3",
            description="V2 Org 3",
            inteligence_organization=3,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_SCALE,
        )

        self.org_auth_1 = self.org_1.authorizations.create(
            user=self.user, role=OrganizationRole.ADMIN.value
        )

        self.org_auth_2 = self.org_2.authorizations.create(
            user=self.user, role=OrganizationRole.CONTRIBUTOR.value
        )

    def make_request(self, path, method, data):
        for key in method:
            if key == "post":
                request = self.factory.post(path, data, format="json")
            elif key == "delete":
                request = self.factory.delete(path)
            else:
                request = self.factory.get(path)
            return request

    def request(self, path: str, method: dict, pk: str = None, data: dict = None, user=None):
        content_data = ""

        if pk:
            path += f"{pk}"

        request = self.make_request(path, method, data)

        force_authenticate(request, user=user, token=user.auth_token)

        response = OrganizationViewSet.as_view(method)(request, uuid=pk, data=data)
        response.render()

        if not response.status_code == status.HTTP_204_NO_CONTENT:
            content_data = json.loads(response.content)
        return response, content_data

    def test_get_organization(self):
        pk = str(self.org_1.uuid)
        path = "/v2/organizations/"
        method = {"get": "retrieve"}
        user = self.user
        auth = self.org_1.get_user_authorization(self.user)
        response, content_data = self.request(
            path,
            method,
            pk=pk,
            user=user
        )

        self.assertEquals(response.status_code, status.HTTP_200_OK)
        self.assertEquals(content_data.get("authorization").get("uuid"), str(auth.uuid))
        self.assertEquals(content_data.get("uuid"), pk)

    def test_fail_get_authorization(self):
        pk = str(self.org_1.uuid)
        path = "/v2/organizations/"
        method = {"get": "retrieve"}
        user = self.user_403

        response, content_data = self.request(
            path,
            method,
            pk=pk,
            user=user
        )
        self.assertEquals(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_organizations(self):
        path = "/v2/organizations/"
        method = {"get": "list"}
        user = self.user
        response, content_data = self.request(
            path,
            method,
            user=user
        )
        self.assertEquals(response.status_code, status.HTTP_200_OK)
        self.assertEquals(content_data.get("count"), 2)

    def test_create_organization(self):
        data = {
            "name": "V2",
            "description": "V2 desc",
            "organization_billing_plan": BillingPlan.PLAN_TRIAL,
            "authorizations": [{"user_email": "e@mail.com", "role": 3}],
        }

        path = "/v2/organizations/"
        method = {"post": "create"}
        user = self.user

        response, content_data = self.request(
            path,
            method,
            user=user,
            data=data
        )
        self.assertEquals(response.status_code, status.HTTP_201_CREATED)

    @patch("connect.api.v1.internal.intelligence.intelligence_rest_client.IntelligenceRESTClient.delete_organization")
    def test_perform_destroy(self, ai_destroy):
        ai_destroy.side_effect = [Response(data={}, status=status.HTTP_204_NO_CONTENT)]
        pk = str(self.org_1.uuid)
        path = "/v2/organizations/"
        method = {"delete": "destroy"}
        user = self.user

        response, content_data = self.request(
            path,
            method,
            pk=pk,
            user=user
        )
