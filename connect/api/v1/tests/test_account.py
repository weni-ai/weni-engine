import json

from django.test import TestCase, RequestFactory
from django.test.client import MULTIPART_CONTENT

from rest_framework import status

from connect.api.v1.account.views import MyUserProfileViewSet
from connect.api.v1.tests.utils import create_user_and_token
from connect.common.models import Organization, BillingPlan, OrganizationRole
from unittest.mock import patch


class ListMyProfileTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user, self.user_token = create_user_and_token()

    def request(self, token):
        authorization_header = {"HTTP_AUTHORIZATION": "Token {}".format(token.key)}
        request = self.factory.get("/v2/account/my-profile/", **authorization_header)
        response = MyUserProfileViewSet.as_view({"get": "retrieve"})(request)
        response.render()
        content_data = json.loads(response.content)
        return (response, content_data)

    def test_okay(self):
        response, content_data = self.request(self.user_token)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(content_data.get("username"), self.user.username)


class UserUpdateTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user, self.user_token = create_user_and_token()

    def request(self, user, data, token):
        authorization_header = {"HTTP_AUTHORIZATION": "Token {}".format(token.key)}
        request = self.factory.patch(
            "/v1/account/my-profile/",
            self.factory._encode_data(data, MULTIPART_CONTENT),
            MULTIPART_CONTENT,
            **authorization_header
        )
        response = MyUserProfileViewSet.as_view({"patch": "update"})(
            request, pk=user.pk, partial=True
        )
        response.render()
        content_data = json.loads(response.content)
        return (response, content_data)

    def test_update_phone(self):
        response, content_data = self.request(
            self.user, {"phone": 996498826, "short_phone_prefix": 55}, self.user_token
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(content_data.get("phone"), 996498826)
        self.assertEqual(content_data.get("short_phone_prefix"), 55)

    def test_update_utm(self):
        response, content_data = self.request(
            self.user, {"utm": json.dumps("{'utm_source': 'weni'}")}, self.user_token
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(content_data.get("utm"), "{'utm_source': 'weni'}")


class DestroyMyProfileTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user, self.user_token = create_user_and_token()

    def request(self, token):
        authorization_header = {"HTTP_AUTHORIZATION": "Token {}".format(token.key)}
        request = self.factory.delete("/v1/account/my-profile/", **authorization_header)
        response = MyUserProfileViewSet.as_view({"delete": "destroy"})(request)
        response.render()
        return response

    def test_okay(self):
        response = self.request(self.user_token)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)


class AdditionalUserInfoTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user, self.user_token = create_user_and_token()

    def request(self, data, token):
        authorization_header = {"HTTP_AUTHORIZATION": "Token {}".format(token.key)}
        request = self.factory.put(
            "/v1/account/my-profile/add_additional_information/",
            data=json.dumps(data),
            content_type="application/json",
            format="json",
            **authorization_header,
        )
        response = MyUserProfileViewSet.as_view({"put": "add_additional_information"})(
            request,
        )
        response.render()
        content_data = json.loads(response.content)
        return (response, content_data)

    def test_okay(self):
        company_info = {
            "name": "test",
            "number_people": "0",
            "segment": "test",
            "sector": "ti",
            "weni_helps": "ti.incidentes",
            "company_phone_number": "5582555555555",
        }

        user_info = {
            "phone": "5582555555555",
            "position": "test_manager",
            "utm": {"utm_source": "instagram"},
        }

        body = dict(
            company=company_info,
            user=user_info
        )

        response, content_data = self.request(body, self.user_token)
        company_response = content_data.get('company')
        user_response = content_data.get('user')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(company_info, company_response)
        self.assertEqual(user_info.get('phone'), user_response.get('phone'))
        self.assertEqual(user_response.get("utm"), {"utm_source": "instagram"})


class CompanyInfoTestCase(TestCase):
    def setUp(self):
        self.owner, self.owner_token = create_user_and_token("owner")
        self.user, self.user_token = create_user_and_token("user")

        owner = self.owner

        owner.company_name = "Test Company"
        owner.company_segment = "Segment"
        owner.company_sector = "Sector"
        owner.number_people = 5
        owner.weni_helps = ""
        owner.save()

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
        self.organization_authorization2 = self.organization.authorizations.create(
            user=self.user, role=OrganizationRole.ADMIN.value
        )

    def request(self, token):
        authorization_header = {"HTTP_AUTHORIZATION": "Token {}".format(token.key)}
        request = self.factory.get("/v1/account/user-company-info/", **authorization_header)
        response = MyUserProfileViewSet.as_view({"get": "get_user_company_info"})(request)
        response.render()
        content_data = json.loads(response.content)
        return (response, content_data)

    def test_okay(self):
        response, content_data = self.request(self.user_token)
        self.assertEquals(list(content_data[0].keys()), ['organization', 'company'])
        self.assertEqual(response.status_code, status.HTTP_200_OK)

@patch("connect.api.v1.keycloak.KeycloakControl.verify_email")
class EmailVerifiedTestCase(TestCase):

    def setUp(self):
        self.owner, self.owner_token = create_user_and_token("owner")
        self.user, self.user_token = create_user_and_token("user")
        self.factory = RequestFactory()
        self.user, self.user_token = create_user_and_token()

    def request(self, token):
        authorization_header = {"HTTP_AUTHORIZATION": "Token {}".format(token.key)}
        request = self.factory.patch(
            "/v1/account/my-profile/verify_email/",
            content_type="application/json",
            format="json",
            **authorization_header,
        )
        response = MyUserProfileViewSet.as_view({"patch": "verify_email"})(request,)
        response.render()
        return response

    def test_okay(self, verify_email):
        response = self.request(self.user_token)
        self.assertEquals(response.status_code, status.HTTP_200_OK)
