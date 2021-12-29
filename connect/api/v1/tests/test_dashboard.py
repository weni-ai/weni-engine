import json
import uuid

from django.test import RequestFactory, TestCase
from rest_framework import status

from connect.api.v1.dashboard.views import StatusServiceViewSet, NewsletterViewSet
from connect.api.v1.tests.utils import create_user_and_token
from connect.common.models import (
    Service,
    Organization,
    OrganizationAuthorization,
    Newsletter,
    NewsletterLanguage,
    BillingPlan,
)


class ListStatusServiceTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

        self.service = Service.objects.create(url="http://test.com", default=True)

        self.user, self.token = create_user_and_token()

        self.organization = Organization.objects.create(
            name="test organization",
            description="",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__payment_method=BillingPlan.PAYMENT_METHOD_CREDIT_CARD,
            organization_billing__plan=BillingPlan.PLAN_ENTERPRISE,
        )

        self.organization_authorization = self.organization.authorizations.create(
            user=self.user, role=OrganizationAuthorization.ROLE_ADMIN
        )

        self.project = self.organization.project.create(
            name="project test",
            timezone="America/Sao_Paulo",
            flow_organization=uuid.uuid4(),
        )

    def request(self, token):
        authorization_header = {"HTTP_AUTHORIZATION": "Token {}".format(token)}
        request = self.factory.get(
            f"/v1/dashboard/status-service/?project_uuid={str(self.project.uuid)}",
            **authorization_header,
        )
        response = StatusServiceViewSet.as_view({"get": "list"})(request)
        response.render()
        content_data = json.loads(response.content)
        return (response, content_data)

    def test_status_okay(self):
        response, content_data = self.request(self.token)
        self.assertEqual(content_data["count"], 1)
        self.assertEqual(len(content_data["results"]), 1)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class ListNewsletterTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

        self.user, self.token = create_user_and_token()

        self.newsletter_en = Newsletter.objects.create()
        self.newsletter_pt_br = Newsletter.objects.create()

        self.newsletter_language_en = NewsletterLanguage.objects.create(
            language="en-us",
            title="Test",
            description="Test description",
            newsletter=self.newsletter_en,
        )

        self.newsletter_language_ptbr = NewsletterLanguage.objects.create(
            language="pt-br",
            title="Teste",
            description="Teste descrição",
            newsletter=self.newsletter_pt_br,
        )

    def request(self, token):
        authorization_header = {"HTTP_AUTHORIZATION": "Token {}".format(token)}
        request = self.factory.get(
            "/v1/dashboard/newsletter/",
            **authorization_header,
        )
        response = NewsletterViewSet.as_view({"get": "list"})(request)
        response.render()
        content_data = json.loads(response.content)
        return (response, content_data)

    def test_status_okay(self):
        response, content_data = self.request(self.token)
        self.assertEqual(content_data["count"], 1)
        self.assertEqual(len(content_data["results"]), 1)
        self.assertEqual(content_data["results"][0].get("language"), "en-us")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_does_not_exist(self):
        self.newsletter_language_en.delete()
        response, content_data = self.request(self.token)
        self.assertEqual(content_data["count"], 0)
        self.assertEqual(len(content_data["results"]), 0)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
