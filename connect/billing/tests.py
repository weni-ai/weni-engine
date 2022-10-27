import uuid
import pendulum
import stripe
import pytz

from datetime import timedelta, datetime
from django.utils import timezone

from unittest import skipIf
from unittest.mock import patch
import uuid as uuid4

from django.test import TestCase
from django.conf import settings

from connect.billing import get_gateway

from connect.billing.models import Contact, Channel, Message, SyncManagerTask
from connect.common.models import Organization, Project, BillingPlan

from freezegun import freeze_time
from connect.billing.tasks import sync_contacts, check_organization_plans


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


@skipIf(True, "Need elastic search and grpc to run this test")
class SyncContactsTestCase(TestCase):
    def setUp(self):
        self.first_sync = SyncManagerTask.objects.create(
            task_type="sync_contacts",
            started_at=pendulum.datetime(2022, 4, 9, 8, 0, 0),
            before=pendulum.datetime(2022, 4, 8, 9, 0, 0),
            after=pendulum.datetime(2022, 4, 8, 4, 0, 0),
            status=True,
            finished_at=pendulum.datetime(2022, 4, 8, 9, 0, 0)
        )

        self.first_count_sync = SyncManagerTask.objects.create(
            task_type="count_contacts",
            started_at=pendulum.datetime(2022, 4, 9, 8, 0, 0),
            before=pendulum.datetime(2022, 4, 8, 9, 0, 0),
            after=pendulum.datetime(2022, 4, 8, 4, 0, 0),
            status=True,
            finished_at=pendulum.datetime(2022, 4, 8, 9, 0, 0)
        )

        self.organization = Organization.objects.create(
            name="test organization",
            description="test organization",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="free",
        )

        self.project = self.organization.project.create(
            name="project test",
            timezone="America/Sao_Paulo",
            flow_organization=uuid.uuid4(),
            flow_id=11
        )

    @freeze_time("2022-04-08 14")
    def test_sync_contacts(self, task):
        task.return_value.result = {
            "uuid": "4b801fbe-5625-41c6-bd99-c872e7aaf99d",
            "text": "Oi",
            "created_on": "2022-03-31 18:06:26.746932+00:00",
            "direction": "I",
            "channel_id": 2,
            "channel_type": "WA",
        }
        sync_contacts()
        last_sync = (
            SyncManagerTask.objects.filter(task_type="sync_contacts")
            .order_by("finished_at")
            .first()
        )

        contacts = Contact.objects.all()

        self.assertEquals(contacts.count(), 1)
        contact = contacts.first()

        self.assertTrue(last_sync.before > contact.last_seen_on)
        self.assertTrue(contact.last_seen_on > last_sync.after)


class ContactTestCase(TestCase):

    def setUp(self):

        self.organization = Organization.objects.create(
            name='org test',
            description='desc',
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__payment_method=BillingPlan.PAYMENT_METHOD_CREDIT_CARD,
            organization_billing__plan=BillingPlan.PLAN_ENTERPRISE
        )

        self.project = Project.objects.create(
            name="project test",
            timezone="America/Sao_Paulo",
            flow_organization=uuid4.uuid4(),
            organization=self.organization
        )

        # self.channel = Channel.objects.create(
        #     name='channel test',
        #     channel_type='WA',
        #     channel_flow_uuid=uuid4.uuid4(),
        #     project=self.project
        # )

        self.contact = Contact.objects.create(
            contact_flow_uuid=uuid4.uuid4(),
            name='contact test 1',
            last_seen_on=datetime(2022, 4, 8, 10, 20, 0, 0, pytz.UTC)
        )

    def test_create_contact(self):
        self.assertEquals(self.contact.name, "contact test 1")
        self.assertEquals(self.contact.last_seen_on, datetime(2022, 4, 8, 10, 20, 0, 0, pytz.UTC))


@skipIf(True, "message not saved yet.")
class MessageTestCase(TestCase):

    def setUp(self):

        self.organization = Organization.objects.create(
            name='org test',
            description='desc',
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__payment_method=BillingPlan.PAYMENT_METHOD_CREDIT_CARD,
            organization_billing__plan=BillingPlan.PLAN_ENTERPRISE
        )

        self.project = Project.objects.create(
            name="project test",
            timezone="America/Sao_Paulo",
            flow_organization=uuid4.uuid4(),
            organization=self.organization
        )

        self.channel = Channel.objects.create(
            name='channel test',
            channel_type='WA',
            channel_flow_uuid=uuid4.uuid4(),
            project=self.project
        )

        self.contact = Contact.objects.create(
            contact_flow_uuid=uuid4.uuid4(),
            name='contact test 1',
            channel=self.channel
        )

        self.message = Message.objects.create(
            contact=self.contact,
            text='test message',
            sent_on=timezone.now(),
            message_flow_uuid=uuid4.uuid4(),
            direction='test'
        )

    def test_create_message(self):
        self.assertTrue("test message", self.message.text)


class CheckPlansTestCase(TestCase):
    def setUp(self):
        # Orgs
        self.basic = Organization.objects.create(
            name="Basic org",
            description="Basic org",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_BASIC,
        )
        self.plus = Organization.objects.create(
            name="plus org",
            description="plus org",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_PLUS,
        )
        self.premium = Organization.objects.create(
            name="premium org",
            description="premium org",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_PREMIUM,
        )
        self.enterprise = Organization.objects.create(
            name="enterprise org",
            description="enterprise org",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_ENTERPRISE,
        )
        # Projects
        self.basic_project = self.basic.project.create(
            name="basic",
            flow_organization=uuid.uuid4(),
        )
        self.plus_project = self.plus.project.create(
            name="plus",
            flow_organization=uuid.uuid4(),
        )
        self.premium_project = self.premium.project.create(
            name="premium",
            flow_organization=uuid.uuid4(),
        )
        self.enterprise_project = self.enterprise.project.create(
            name="enterprise",
            flow_organization=uuid.uuid4(),
        )

    def test_task_end_trial_plan(self):
        """
        Test if 'check_organization_plans' suspends org that should after the trial periods end
        """

        check_organization_plans()

        for org in Organization.objects.all():
            self.assertGreater(org.active_contacts, org.organization_billing.plan_limit)
            self.assertTrue(org.is_suspended)
