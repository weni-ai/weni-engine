import pytz
import pendulum
import uuid as uuid4
from unittest import skipIf
from django.test import TestCase
from django.conf import settings
from datetime import datetime
from connect.common.models import Organization, BillingPlan
from connect.elastic.flow import ElasticFlow


@skipIf(not settings.FLOWS_ELASTIC_URL, "Elastic search not configured")
class ElasticSearchTestCase(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="Test",
            inteligence_organization=0,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="free",
        )
        # ajust flow_id and other infos to the data in your es index
        self.project = self.organization.project.create(
            name="project test",
            timezone="America/Sao_Paulo",
            flow_organization=uuid4.uuid4(),
            flow_id=11,
        )

        self.client = ElasticFlow()

    def test_contact_active(self):
        after = datetime(2022, 4, 8, 10, 20, 0, 0, pytz.UTC)
        before = datetime(2022, 4, 8, 15, 20, 0, 0, pytz.UTC)

        response = self.client.get_contact_detailed(
            self.project.flow_id, str(before), str(after)
        )
        hit = list(response)[0]
        last_seen_on = pendulum.parse(hit.last_seen_on)

        self.assertEquals(len(response), 1)
        self.assertEquals(hit.org_id, self.project.flow_id)
        self.assertTrue(hit.is_active)
        self.assertLess(last_seen_on, before)
        self.assertGreaterEqual(last_seen_on, after)
