import uuid
import random
import pendulum
from django.test import TestCase
from connect.common.models import Project, Organization, BillingPlan
from connect.billing.models import Contact, ContactCount
from connect.billing.tasks import daily_contact_count
from connect.utils import count_contacts
from freezegun import freeze_time


@freeze_time("2022-05-14")
class CountContactsTestCase(TestCase):
    def setUp(self) -> None:
        self.organization = Organization.objects.create(
            name="test organization",
            description="test organization",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="free",
        )

        self.organization2 = Organization.objects.create(
            name="test organization 2",
            description="test organization 2",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="enterprise",
        )

        self.custom = Organization.objects.create(
            name="custom organization",
            description="custom organization",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="custom",
        )

        self.project = self.organization.project.create(
            name="Project 1",
            timezone="America/Sao_Paulo",
            flow_organization=uuid.uuid4(),
        )

        self.project2 = self.organization.project.create(
            name="Project 2",
            timezone="America/Sao_Paulo",
            flow_organization=uuid.uuid4(),
        )

        self.project3 = self.organization2.project.create(
            name="Project 3",
            timezone="America/Sao_Paulo",
            flow_organization=uuid.uuid4(),
        )

        self.project4 = self.organization2.project.create(
            name="Project 4",
            timezone="America/Sao_Paulo",
            flow_organization=uuid.uuid4(),
        )

        self.cproject2 = self.custom.project.create(
            name="Custom Project 3",
            timezone="America/Sao_Paulo",
            flow_organization=uuid.uuid4(),
        )

        self.cproject1 = self.custom.project.create(
            name="Custom Project 4",
            timezone="America/Sao_Paulo",
            flow_organization=uuid.uuid4(),
        )

        self.create_contacts()

        return super().setUp()

    def create_contacts(self):
        day = pendulum.now().start_of("day")

        contact_list = []

        for project in Project.objects.all():
            for j in range(0, 100):
                if j == 0 or j % 5 == 0:
                    contact_flow_uuid = uuid.uuid4()
                    last_seen_on = day.add(hours=random.randint(0, 23))
                    last_seen_on2 = day.add(days=1).add(hours=random.randint(0, 23))
                    last_seen_on3 = day.add(days=2).add(hours=random.randint(0, 23))

                contact = Contact(
                    contact_flow_uuid=contact_flow_uuid,
                    last_seen_on=last_seen_on,
                    project=project,
                )
                contact2 = Contact(
                    contact_flow_uuid=contact_flow_uuid,
                    last_seen_on=last_seen_on2,
                    project=project,
                )
                contact3 = Contact(
                    contact_flow_uuid=contact_flow_uuid,
                    last_seen_on=last_seen_on3,
                    project=project,
                )

                contact_list.extend([contact, contact2, contact3])

        Contact.objects.bulk_create(contact_list)

    def test_count(self):
        daily_contact_count()
        for project in Project.objects.exclude(organization__organization_billing__plan=BillingPlan.PLAN_CUSTOM):
            contacts_day_count = ContactCount.objects.filter(project=project, day=pendulum.now().start_of("day"))
            total = sum([day_count.count for day_count in contacts_day_count])
            self.assertEquals(total, 20)

    def test_count_contacts(self):
        """If organization's plan == Custom, uses the old way of counting contacts (Contact active per month).
            else use daily contact count.
        """

        before = pendulum.now().end_of("month")
        after = pendulum.now().start_of("month")

        for i in range(0, before.day):
            freezer = freeze_time(after.add(days=i))
            freezer.start()
            daily_contact_count()
            freezer.stop()

        for org in Organization.objects.all():

            contact_count = 0

            for project in org.project.all():
                total = count_contacts(project=project, before=str(before), after=str(after))
                contact_count += total

            if org.organization_billing.plan in [BillingPlan.PLAN_CUSTOM, BillingPlan.PLAN_ENTERPRISE]:
                self.assertEqual(contact_count, 40)
            else:
                self.assertEqual(contact_count, 120)
