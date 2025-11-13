from django.test import TestCase
from django.urls import reverse

from connect.authentication.models import User
from connect.common.models import Organization, BillingPlan


class OrganizationAdminSearchTestCase(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            email="admin@example.com", username="admin", password="pass"
        )
        self.client.force_login(self.admin_user)

        self.org1 = Organization.objects.create(
            name="Org One",
            inteligence_organization=0,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="free",
        )
        self.org2 = Organization.objects.create(
            name="Org Two",
            inteligence_organization=0,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="free",
        )

    def test_admin_search_by_uuid_returns_exact_organization(self):
        changelist_url = reverse("admin:common_organization_changelist")
        response = self.client.get(changelist_url, {"q": str(self.org1.uuid)})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.org1.name)
        self.assertNotContains(response, self.org2.name)

    def test_admin_search_by_nonexistent_uuid_returns_empty(self):
        changelist_url = reverse("admin:common_organization_changelist")
        response = self.client.get(
            changelist_url, {"q": "00000000-0000-0000-0000-000000000000"}
        )
        self.assertEqual(response.status_code, 200)
        # Should not list created orgs when searching a non-existent UUID
        self.assertNotContains(response, self.org1.name)
        self.assertNotContains(response, self.org2.name)
