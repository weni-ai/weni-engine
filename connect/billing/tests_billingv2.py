import uuid
import random
import pendulum
from django.test import TestCase
from connect.common.models import Project, Organization, BillingPlan
from connect.billing.models import Contact, ContactCount
from connect.billing.tasks import daily_contact_count


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

        self.mock_contacts()

        return super().setUp()

    def mock_contacts(self):
        today = pendulum.now().start_of("day")

        for project in Project.objects.all():
            day = today
            for i in range(1, 3):
                # daily contacts
                contacts_list = []

                for j in range(0, 100):
                    # active contacts multiple times a day
                    if (j == 0 or j % 5 == 0):
                        contact_flow_uuid = uuid.uuid4()
                        last_seen_on = day.add(hours=random.randint(0, 23))
                    contact = Contact(
                        contact_flow_uuid=contact_flow_uuid,
                        last_seen_on=last_seen_on,
                        project=project,
                    )
                    contacts_list.append(contact)
                Contact.objects.bulk_create(contacts_list)
                day = today.subtract(days=i)

    def test_count(self):
        self.mock_contacts()
        daily_contact_count()

        for project in Project.objects.all():
            contacts_day_count = ContactCount.objects.filter(project=project, day=pendulum.now().start_of("day"))
            total = sum([day_count.count for day_count in contacts_day_count])
            self.assertEquals(total, 40)
