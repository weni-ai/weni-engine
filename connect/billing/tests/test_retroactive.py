import pendulum
from connect.billing.models import SyncManagerTask, Contact
from connect.common.models import Organization, Project, BillingPlan
from django.test import TestCase
from connect.billing.tests.helpers import get_active_contacts
import uuid


class RetroactiveContactsTestCase(TestCase):
    def setUp(self) -> None:

        self.after = pendulum.now().subtract(months=1).end_of("month")
        self.before = self.after.add(days=1).start_of("day")

        self.last_retroactive_sync = SyncManagerTask.objects.create(
            task_type="retroactive_sync",
            status=True,
            before=self.before,
            after=self.after,
            started_at=pendulum.now().subtract(minutes=5),
            finished_at=pendulum.now()
        )

        self.organization = Organization.objects.create(
            name="test organization",
            description="test organization",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="free",
        )

        self.organization2 = Organization.objects.create(
            name="test organization 2",
            description="test organization",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="free",
        )

        self.organization.project.create(
            name="project test",
            timezone="America/Sao_Paulo",
            flow_organization=uuid.uuid4(),
            flow_id=1
        )

        self.organization.project.create(
            name="project test 2",
            timezone="America/Sao_Paulo",
            flow_organization=uuid.uuid4(),
            flow_id=2
        )

        self.organization2.project.create(
            name="project test 3",
            timezone="America/Sao_Paulo",
            flow_organization=uuid.uuid4(),
            flow_id=3
        )

        self.organization2.project.create(
            name="project test 4",
            timezone="America/Sao_Paulo",
            flow_organization=uuid.uuid4(),
            flow_id=4
        )

    def test_sync_contacts_retroactive(self):

        last_retroactive_sync = self.last_retroactive_sync

        if last_retroactive_sync:
            after = pendulum.instance(last_retroactive_sync.before)
            before = after.add(days=1)

        manager = SyncManagerTask.objects.create(
            task_type="retroactive_sync",
            started_at=pendulum.now(),
            before=before,
            after=after,
        )
        try:
            # flow_instance = utils.get_grpc_types().get("flow")
            for project in Project.objects.exclude(flow_id=None):
                active_contacts = get_active_contacts(
                    str(project.flow_organization),
                    manager.before.strftime("%Y-%m-%d %H:%M"),
                    manager.after.strftime("%Y-%m-%d %H:%M"),
                )
                bulk_contacts = []
                for active_contact in active_contacts:
                    ts = f"{active_contact.msg.sent_on.seconds.real}.{active_contact.msg.sent_on.nanos.real}"
                    contact = Contact(
                        contact_flow_uuid=active_contact.uuid,
                        name=active_contact.name,
                        last_seen_on=pendulum.from_timestamp(float(ts)),
                        project=project,
                    )
                    bulk_contacts.append(contact)

                Contact.objects.bulk_create(bulk_contacts)

            manager.finished_at = pendulum.now()
            manager.status = True
            manager.save(update_fields=["finished_at", "status"])
        except Exception as error:
            print(error)
            manager.finished_at = pendulum.now()
            manager.fail_message.create(message=str(error))
            manager.status = False
            manager.save(update_fields=["finished_at", "status"])

        for project in Project.objects.all():
            count = Contact.objects.filter(project=project).filter(last_seen_on__range=(after, before)).count()
            self.assertEquals(count, 10)
        self.assertEquals(manager.before, before)
        self.assertTrue(manager.status)
