import json
import uuid as uuid4
from unittest.mock import patch
from datetime import timedelta
from django.conf import settings
from django.test import RequestFactory
from django.test import TestCase
from django.utils import timezone
from rest_framework import status

from connect.api.v1.invoice.views import InvoiceViewSet
from connect.api.v1.tests.utils import create_user_and_token
from connect.common.models import (
    OrganizationAuthorization,
    Organization,
    BillingPlan,
)


class CeleryResponse:
    def __init__(self, response):
        self.result = response

    def wait(self):
        ...


class ListInvoiceAPITestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.owner, self.owner_token = create_user_and_token("owner")

        self.organization = Organization.objects.create(
            name="test organization",
            description="",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_DAYS.get(
                BillingPlan.BILLING_CYCLE_MONTHLY
            ),
            organization_billing__payment_method=BillingPlan.PAYMENT_METHOD_CREDIT_CARD,
            organization_billing__plan=BillingPlan.PLAN_ENTERPRISE,
        )
        self.organization_authorization = self.organization.authorizations.create(
            user=self.owner, role=OrganizationAuthorization.ROLE_ADMIN
        )
        self.project = self.organization.project.create(
            name="project test",
            timezone="America/Sao_Paulo",
            flow_organization=uuid4.uuid4(),
        )

    def request(self, param, value, token=None):
        authorization_header = (
            {"HTTP_AUTHORIZATION": "Token {}".format(token.key)} if token else {}
        )

        request = self.factory.get(
            "/v1/organization/project/?{}={}".format(param, value),
            **authorization_header,
        )

        response = InvoiceViewSet.as_view({"get": "list"})(request)
        response.render()
        content_data = json.loads(response.content)
        return (response, content_data)

    def test_okay(self):
        self.organization.organization_billing_invoice.create(
            due_date=timezone.now() + timedelta(days=10),
            invoice_random_id=1
            if self.organization.organization_billing_invoice.last() is None
            else self.organization.organization_billing_invoice.last().invoice_random_id
            + 1,
            discount=self.organization.organization_billing.fixed_discount,
            extra_integration=self.organization.extra_integration,
            cost_per_whatsapp=settings.BILLING_COST_PER_WHATSAPP,
        )
        response, content_data = self.request(
            "organization",
            self.organization.uuid,
            self.owner_token,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(content_data.get("count"), 1)


class InvoiceDataTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.owner, self.owner_token = create_user_and_token("owner")

        self.organization = Organization.objects.create(
            name="test organization",
            description="",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_DAYS.get(
                BillingPlan.BILLING_CYCLE_MONTHLY
            ),
            organization_billing__payment_method=BillingPlan.PAYMENT_METHOD_CREDIT_CARD,
            organization_billing__plan=BillingPlan.PLAN_ENTERPRISE,
        )
        self.organization_authorization = self.organization.authorizations.create(
            user=self.owner, role=OrganizationAuthorization.ROLE_ADMIN
        )
        self.project = self.organization.project.create(
            name="project test",
            timezone="America/Sao_Paulo",
            flow_organization=uuid4.uuid4(),
        )
        self.invoice = self.invoice = self.organization.organization_billing_invoice.create(
            due_date=timezone.now() + timedelta(days=30),
            invoice_random_id=1
            if self.organization.organization_billing_invoice.last() is None else self.organization.organization_billing_invoice.last().invoice_random_id + 1,
            discount=self.organization.organization_billing.fixed_discount,
            extra_integration=self.organization.extra_integration,
            cost_per_whatsapp=settings.BILLING_COST_PER_WHATSAPP,
            stripe_charge='ch_3K9wZYGB60zUb40p1C0iiskn',
            payment_method=BillingPlan.PAYMENT_METHOD_CREDIT_CARD
        )

    def request(self, value, invoice_id, token=None):
        authorization_header = (
            {"HTTP_AUTHORIZATION": "Token {}".format(token.key)} if token else {}
        )
        request = self.factory.get(
            f"/v1/organization/invoice/invoice-data/{value}/?invoice_id={invoice_id}", **authorization_header
        )
        response = InvoiceViewSet.as_view({"get": "invoice_data"})(
            request, organization_uuid=self.organization.uuid
        )
        content_data = json.loads(response.content)

        return response, content_data

    @patch("connect.celery.app.send_task")
    def test_okay(self, task):
        task.side_effect = [
            CeleryResponse(dict(active_contacts=0)),
        ]
        response, content_data = self.request(
            self.organization.uuid,
            1,
            self.owner_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(content_data['payment_data'], {'payment_method': 'credit_card', 'card_data': {'brand': 'visa', 'last4': '4242'}, 'projects': [{'project_name': 'project test', 'contact_count': 0}], 'price': '267.00'})
