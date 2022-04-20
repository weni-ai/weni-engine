import uuid
import stripe

from datetime import timedelta
from django.utils import timezone

from unittest import skipIf
from unittest.mock import patch

from django.test import TestCase
from connect.billing import get_gateway

from django.conf import settings
from connect.billing.models import Channel, SyncManagerTask
from connect.common.models import Organization, BillingPlan


@skipIf(not settings.BILLING_SETTINGS.get("stripe", None), "gateway not configured")
class StripeGatewayTestCase(TestCase):
    def setUp(self):
        self.merchant = get_gateway("stripe")
        stripe.api_key = self.merchant.stripe.api_key
        self.stripe = stripe
        self.customer = "cus_KzFc41F3yLCLoO"

    def testPurchase(self):
        resp = self.merchant.purchase(10, self.customer)
        self.assertEquals(resp["status"], "SUCCESS")

    def testPurchaseDecimalAmount(self):
        resp = self.merchant.purchase(10.99, self.customer)
        self.assertEquals(resp["status"], "SUCCESS")

    def test_last_2(self):
        resp = self.merchant.get_card_data(self.customer)
        self.assertEquals(resp['response'][0]['last2'], '42')

    def test_brand(self):
        resp = self.merchant.get_card_data(self.customer)
        self.assertEquals(resp['response'][0]['brand'], 'visa')

    def test_get_card_data(self):
        resp = self.merchant.get_card_data(self.customer)
        self.assertEquals(resp['status'], 'SUCCESS')

    def test_get_user_detail_data(self):
        resp = self.merchant.get_user_detail_data(self.customer)
        self.assertEquals(resp['status'], 'SUCCESS')

    def test_get_payment_method_details(self):
        resp = self.merchant.get_payment_method_details("ch_3K9wZYGB60zUb40p1C0iiskn")
        self.assertEquals(resp['status'], 'SUCCESS')
        self.assertEquals(resp['response']['final_card_number'], '4242')
        self.assertEquals(resp['response']['brand'], 'visa')

    def test_get_payment_method_details_fail(self):
        resp = self.merchant.get_payment_method_details("ch_3K9wZYGB60zUb40p1C0iisk")
        self.assertEquals(resp['status'], 'FAIL')


class ChannelTestCase(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="test organization",
            description="",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__payment_method=BillingPlan.PAYMENT_METHOD_CREDIT_CARD,
            organization_billing__plan=BillingPlan.PLAN_ENTERPRISE,
        )
        self.project = self.organization.project.create(
            name="project test",
            timezone="America/Sao_Paulo",
            flow_organization=uuid.uuid4(),
        )
        self.channel_flow_uuid = uuid.uuid4()

    def test_create_model(self):
        channel = Channel.objects.create(
            project=self.project,
            channel_flow_uuid=self.channel_flow_uuid,
            channel_type="WA",
            name="Test Channel"
        )
        same_channel = Channel.create(
            project=self.project,
            channel_flow_uuid=self.channel_flow_uuid,
            channel_type="WA",
            name="Test Channel"
        )
        self.assertAlmostEquals(channel.channel_flow_uuid, self.channel_flow_uuid)
        self.assertAlmostEquals(same_channel.channel_flow_uuid, self.channel_flow_uuid)


class SyncManagerTest(TestCase):
    def setUp(self):
        self.manager = SyncManagerTask.objects.create(
            task_type="sync_contacts",
            started_at=timezone.now(),
            before=timezone.now(),
            after=(timezone.now() - timedelta(hours=5)),
        )

    @patch("connect.billing.tasks.sync_contacts.delay")
    def test_ok(self, task):
        # task run sucessfully
        task.return_value.result = True
        self.manager.finished_at = timezone.now()
        self.manager.status = task.return_value.result
        self.manager.save(update_fields=["finished_at", "status"])
        self.assertEquals(self.manager.status, True)

    @patch("connect.billing.tasks.sync_contacts.delay")
    def test_fail(self, task):
        task.return_value.result = False
        self.manager.finished_at = timezone.now()
        self.manager.status = task.return_value.result
        self.manager.save(update_fields=["finished_at", "status"])
        self.assertEquals(self.manager.status, False)
