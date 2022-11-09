import uuid
from django.test import TestCase
from connect.authentication.models import User
from connect.common.models import Organization, OrganizationRole, BillingPlan  # , Project
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
