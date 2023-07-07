import uuid as uuid4
from django.test import TestCase
from django.core import mail
from django.conf import settings
from connect.authentication.models import User
from connect.common.models import Organization, OrganizationRole, BillingPlan, Project
from connect.api.v1.tests.utils import create_user_and_token
from connect.common.mocks import StripeMockGateway
from unittest.mock import patch
from unittest import skipIf


@skipIf(True, "")
class BillingPlanTestCase(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner@user.com", "owner")
        # TRIAL
        self.organization = Organization.objects.create(
            name="Test Features (trial)",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
            organization_billing__stripe_customer="cus_MYOrndkgpPHGK9"
        )
        self.organization_authorization = self.organization.authorizations.create(
            user=self.owner, role=OrganizationRole.ADMIN.value
        )

        # BASIC
        self.basic = Organization.objects.create(
            name="Test Features (start)",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_START,
            organization_billing__stripe_customer="cus_MYOrndkgpPHGK9"
        )
        self.basic_authorization = self.basic.authorizations.create(
            user=self.owner, role=OrganizationRole.ADMIN.value
        )

        self.p1 = self.basic.project.create(
            name="project test",
            timezone="America/Sao_Paulo",
            flow_organization=uuid.uuid4(),
            contact_count=44,
        )
        self.p2 = self.basic.project.create(
            name="project test 2",
            timezone="America/Sao_Paulo",
            flow_organization=uuid.uuid4(),
            contact_count=56,
        )

    def test_trial(self):
        billing = self.organization.organization_billing
        print(self.organization)
        fields = [x for x in self.organization.organization_billing.__dict__.keys() if not x.startswith('_')]
        print("[+]ATTRIBUTES[+]")
        for field in fields:
            print(f"{field} = {billing.__dict__[field]}")

        print("\n[+]METHODS[+]")
        print(f"PLAN: {billing.plan}")
        print(f"PLAN LIMIT: {billing.plan_limit}")
        print(f"STRIPE CUSTOMER: {billing.get_stripe_customer.id}")
        print(f"INVOICE WARNING: {billing.invoice_warning}")
        print(f"ALLOW PAYMENTS: {billing.allow_payments()}")
        print(f"PROBLEM CAPTURE INVOICE: {billing.problem_capture_invoice}")
        print(f"PAYMENT WARNINGS: {billing.payment_warnings}")
        # print(f'{"remove credit card".upper()}: {billing.remove_credit_card}')
        print(f'{"calculate amount".upper()}: {billing.calculate_amount(1)}')
        print(f'{"is card valid".upper()}: {billing.is_card_valid}')
        print(f'{"currenty invoice".upper()}: {billing.currenty_invoice}')
        # print(f'{"change plan".upper()}: {billing.change_plan(BillingPlan.PLAN_START)}')
        # print(f'{"add additional information".upper()}: {billing.add_additional_information({})}')
        print(f'{"end trial period".upper()}: {billing.end_trial_period()}')

        for field in fields:
            if field:
                print(f"{field} = {billing.__dict__[field]}")

    def test_basic(self):
        print(self.basic)
        billing = self.basic.organization_billing
        fields = [x for x in self.basic.organization_billing.__dict__.keys() if not x.startswith('_')]
        print("[+]ATTRIBUTES[+]")
        for field in fields:
            print(f"{field} = {billing.__dict__[field]}")

        print("\n[+]METHODS[+]")
        print(f"PLAN: {billing.plan}")
        print(f"PLAN LIMIT: {billing.plan_limit}")
        print(f"STRIPE CUSTOMER: {billing.get_stripe_customer.id}")
        print(f"INVOICE WARNING: {billing.invoice_warning}")
        print(f"ALLOW PAYMENTS: {billing.allow_payments()}")
        print(f"PROBLEM CAPTURE INVOICE: {billing.problem_capture_invoice}")
        print(f"PAYMENT WARNINGS: {billing.payment_warnings}")
        # print(f'{"remove credit card".upper()}: {billing.remove_credit_card}')
        print(f'{"calculate amount".upper()}: {billing.calculate_amount(1)}')
        print(f'{"is card valid".upper()}: {billing.is_card_valid}')
        print(f'{"currenty invoice".upper()}: {billing.currenty_invoice}')
        # print(f'{"change plan".upper()}: {billing.change_plan(BillingPlan.PLAN_START)}')
        # print(f'{"add additional information".upper()}: {billing.add_additional_information({})}')
        print(f'{"end trial period".upper()}: {billing.end_trial_period()}')

        for field in fields:
            if field:
                print(f"{field} = {billing.__dict__[field]}")


class ProjectEmailTestCase(TestCase):

    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway):

        mock_get_gateway.return_value = StripeMockGateway()

        self.user, self.token = create_user_and_token()
        self_test_org = Organization.objects.create(
            name="Test Organization",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_START,
        )
        self.test_project = Project.objects.create(
            name="Test Project",
            organization=self_test_org
        )
        self.test_email = "test@example.com"
        self.test_first_name = "Test User"

    def test_send_email_change_project(self):

        self.info = {
            "old_project_name": "Old Project",
            "date_before": "2022-01-01",
            "old_timezone": "America/New_York",
            "country_loc_suport_before": "USA",
            "country_loc_suport_now": "Canada",
            "default_lang_before": "English",
            "default_lang_now": "French",
            "secondary_lang_before": "Spanish",
            "secondary_lang_now": "Spanish",
            "user": "John Doe",
        }
        self.test_project.send_email_change_project(
            self.test_first_name, self.test_email, self.info
        )

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            mail.outbox[0].subject, f"The project {self.test_project.name} has changed"
        )
        self.assertEqual(mail.outbox[0].from_email, settings.DEFAULT_FROM_EMAIL)
        self.assertEqual(mail.outbox[0].to, [self.test_email])

    def test_send_email_deleted_project(self):
        self.test_project.send_email_deleted_project(
            self.test_first_name, self.test_email
        )
        self.assertEqual(len(mail.outbox), 1)
        outbox = mail.outbox[0]
        self.assertEqual(outbox.subject, "A project was deleted...")
        self.assertEqual(outbox.from_email, settings.DEFAULT_FROM_EMAIL)
        self.assertEqual(outbox.to[0], self.test_email)
