import json
import uuid
import pendulum
from datetime import timedelta

from django.utils import timezone
from django.test import RequestFactory, TestCase
from rest_framework import status
from connect.api.v1.dashboard.views import StatusServiceViewSet, NewsletterViewSet
from connect.api.v1.dashboard.serializers import StatusServiceSerializer
from connect.api.v1.tests.utils import create_user_and_token
from connect.common.models import (
    Service,
    LogService,
    Organization,
    Project,
    Newsletter,
    NewsletterLanguage,
    NewsletterOrganization,
    BillingPlan,
    OrganizationRole,
    ServiceStatus,
)
from connect.common.mocks import StripeMockGateway
from unittest.mock import patch


class ListStatusServiceTestCase(TestCase):
    @patch("connect.common.signals.update_user_permission_project")
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway, mock_permission):
        self.factory = RequestFactory()

        self.service = Service.objects.create(url="http://test.com", default=True)

        self.user, self.token = create_user_and_token()

        mock_get_gateway.return_value = StripeMockGateway()
        mock_permission.return_value = True

        self.organization = Organization.objects.create(
            name="test organization",
            description="",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__payment_method=BillingPlan.PAYMENT_METHOD_CREDIT_CARD,
            organization_billing__plan=BillingPlan.PLAN_ENTERPRISE,
        )

        self.organization_authorization = self.organization.authorizations.create(
            user=self.user, role=OrganizationRole.ADMIN.value
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
        self.assertEqual(len(content_data), 1)
        self.assertEqual(content_data[0].get("language"), "en-us")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_does_not_exist(self):
        self.newsletter_language_en.delete()
        response, content_data = self.request(self.token)
        self.assertEqual(len(content_data), 0)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class ListNewsletterOrgTestCase(TestCase):
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway):
        self.factory = RequestFactory()
        self.user, self.token = create_user_and_token()
        mock_get_gateway.return_value = StripeMockGateway()
        self.organization = Organization.objects.create(
            name="ASDF",
            description="ASDF",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__payment_method=BillingPlan.PAYMENT_METHOD_CREDIT_CARD,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        self.organization_authorization = self.organization.authorizations.create(
            user=self.user, role=OrganizationRole.ADMIN.value
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

    def test_newsletter_trial_end(self):
        self.organization.organization_billing.end_trial_period()

        response, content_data = self.request(self.token)
        newsletter = content_data[0]

        self.assertEquals(
            pendulum.parse(newsletter.get("trial_end_date")),
            self.organization.organization_billing.trial_end_date,
        )
        self.assertEquals(newsletter.get("title"), "trial-ended")

    def test_newsletter_trial_about_to_end(self):
        NewsletterOrganization.objects.create(
            newsletter=Newsletter.objects.create(),
            title="trial-about-to-end",
            description=f"Your trial period of the organization {self.organization.name}, is about to expire.",
            organization=self.organization,
        )

        response, content_data = self.request(self.token)

        newsletter = content_data[0]
        self.assertEquals(newsletter.get("title"), "trial-about-to-end")


class StatusServiceSerializerTestCase(TestCase):
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway):
        mock_get_gateway.return_value = StripeMockGateway()
        self.service = Service.objects.create(url="http://test.com", default=False)
        self_test_org = Organization.objects.create(
            name="Test Organization",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_START,
        )
        self.project = Project.objects.create(
            name="Test Project", organization=self_test_org
        )
        self.service_status = ServiceStatus.objects.create(
            service=self.service, project=self.project
        )
        self.serializer = StatusServiceSerializer(instance=self.service_status)

    def test_service__status_offline(self):
        self.service.maintenance = False
        self.create_service_logs(total_fail=5, total_success=0)
        self.assertEqual(
            self.serializer.data["service__status"]["status"],
            "offline",
            msg="Should return 'offline' status",
        )

    def test_service__status_maintenance(self):
        self.service.maintenance = True
        self.service.save()
        self.assertEqual(
            self.serializer.data["service__status"]["status"],
            "maintenance",
            msg="Should return 'maintenance' status",
        )

    def test_service__status_intermittent(self):
        self.service.maintenance = False
        self.create_service_logs(total_fail=2, total_success=1)
        self.assertEqual(
            self.serializer.data["service__status"]["status"],
            "intermittent",
            msg="Should return 'intermittent' status",
        )

    def create_service_logs(self, total_fail, total_success):
        now = timezone.now()
        for _ in range(total_fail):
            self.create_log_object(status=False, created_at=now - timedelta(minutes=10))
        for _ in range(total_success):
            self.create_log_object(status=True, created_at=now - timedelta(minutes=10))

    def create_log_object(self, status, created_at):
        log_test = LogService.objects.create(
            status=status, created_at=created_at, service=self.service
        )
        return log_test
