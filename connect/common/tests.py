import uuid as uuid4

from django.test import TestCase

from connect.authentication.models import User
from connect.common.models import (
    Newsletter,
    Service,
    Organization,
    OrganizationAuthorization,
    ServiceStatus,
    NewsletterLanguage,
    BillingPlan,
    GenericBillingData
)
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


class NewsletterTestCase(TestCase):
    def test_newsletter_create(self):
        title = "New feature"
        description = "test description"
        newsletter = Newsletter.objects.create()

        newsletter_language = NewsletterLanguage.objects.create(
            title=title, description=description, newsletter=newsletter
        )

        self.assertEqual(newsletter_language.title, title)
        self.assertEqual(newsletter_language.description, description)


class ServiceStatusTestCase(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner@user.com", "owner")

        self.organization = Organization.objects.create(
            name="Test", inteligence_organization=0,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="free",
        )
        self.project = self.organization.project.create(
            name="project test",
            timezone="America/Sao_Paulo",
            flow_organization=uuid4.uuid4(),
        )
        self.service = Service.objects.create(url="http://test.com", default=False)

    def test_create_service_status(self):
        status = ServiceStatus.objects.create(
            service=self.service,
            project=self.project,
        )
        self.service.log_service.create(status=False)
        self.assertEqual(status.service.url, "http://test.com")
        self.assertEqual(self.service.log_service.first().status, False)
        self.assertEqual(status.service.default, False)
        self.assertEqual(str(status.service), status.service.url)

    def test_create_service_default(self):
        service = Service.objects.create(url="http://test-default.com", default=True)
        log_service = service.log_service.create(status=True)
        self.assertEqual(
            self.project.service_status.all().first().service.url, service.url
        )
        self.assertEqual(
            self.project.service_status.all()
            .first()
            .service.log_service.first()
            .status,
            log_service.status,
        )
        self.assertEqual(
            self.project.service_status.all().first().service.default, service.default
        )


class OrganizationAuthorizationTestCase(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner@user.com", "owner")
        self.user = User.objects.create_user("fake@user.com", "user")

        self.organization = Organization.objects.create(
            name="Test", inteligence_organization=0,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="free",
        )
        self.organization_authorization = self.organization.authorizations.create(
            user=self.owner, role=OrganizationAuthorization.ROLE_ADMIN
        )

    def test_admin_level(self):
        authorization = self.organization.get_user_authorization(self.owner)
        self.assertEqual(authorization.level, OrganizationAuthorization.LEVEL_ADMIN)

    def test_not_read_level(self):
        authorization = self.organization.get_user_authorization(self.user)
        self.assertNotEqual(authorization.level, OrganizationAuthorization.LEVEL_VIEWER)

    def test_can_read(self):
        # organization owner
        authorization_owner = self.organization.get_user_authorization(self.owner)
        self.assertTrue(authorization_owner.can_read)
        # secondary user in private organization
        private_authorization_user = self.organization.get_user_authorization(self.user)
        self.assertFalse(private_authorization_user.can_read)

    def test_can_contribute(self):
        # organization owner
        authorization_owner = self.organization.get_user_authorization(self.owner)
        self.assertTrue(authorization_owner.can_contribute)
        # secondary user in public organization
        authorization_user = self.organization.get_user_authorization(self.user)
        self.assertFalse(authorization_user.can_contribute)
        # private organization owner
        private_authorization_owner = self.organization.get_user_authorization(
            self.owner
        )
        self.assertTrue(private_authorization_owner.can_contribute)
        # secondary user in private organization
        private_authorization_user = self.organization.get_user_authorization(self.user)
        self.assertFalse(private_authorization_user.can_contribute)

    def test_can_write(self):
        # organization owner
        authorization_owner = self.organization.get_user_authorization(self.owner)
        self.assertTrue(authorization_owner.can_write)
        # secondary user in public organization
        authorization_user = self.organization.get_user_authorization(self.user)
        self.assertFalse(authorization_user.can_write)
        # private organization owner
        private_authorization_owner = self.organization.get_user_authorization(
            self.owner
        )
        self.assertTrue(private_authorization_owner.can_write)
        # secondary user in private organization
        private_authorization_user = self.organization.get_user_authorization(self.user)
        self.assertFalse(private_authorization_user.can_write)

    def test_is_admin(self):
        # organization owner
        authorization_owner = self.organization.get_user_authorization(self.owner)
        self.assertTrue(authorization_owner.is_admin)
        # secondary user in public organization
        authorization_user = self.organization.get_user_authorization(self.user)
        self.assertFalse(authorization_user.is_admin)
        # private organization owner
        private_authorization_owner = self.organization.get_user_authorization(
            self.owner
        )
        self.assertTrue(private_authorization_owner.is_admin)
        # secondary user in private organization
        private_authorization_user = self.organization.get_user_authorization(self.user)
        self.assertFalse(private_authorization_user.is_admin)

    def test_owner_ever_admin(self):
        authorization_owner = self.organization.get_user_authorization(self.owner)
        self.assertTrue(authorization_owner.is_admin)

    def test_role_user_can_read(self):
        # public organization
        authorization_user = self.organization.get_user_authorization(self.user)
        authorization_user.role = OrganizationAuthorization.ROLE_VIEWER
        authorization_user.save()
        self.assertTrue(authorization_user.can_read)

        # private organization
        authorization_user = self.organization.get_user_authorization(self.user)
        authorization_user.role = OrganizationAuthorization.ROLE_VIEWER
        authorization_user.save()
        self.assertTrue(authorization_user.can_read)

    def test_role_user_can_t_contribute(self):
        # public organization
        authorization_user = self.organization.get_user_authorization(self.user)
        authorization_user.role = OrganizationAuthorization.ROLE_VIEWER
        authorization_user.save()
        self.assertFalse(authorization_user.can_contribute)

        # private organization
        authorization_user = self.organization.get_user_authorization(self.user)
        authorization_user.role = OrganizationAuthorization.ROLE_VIEWER
        authorization_user.save()
        self.assertFalse(authorization_user.can_contribute)

    def test_role_contributor_can_contribute(self):
        # public organization
        authorization_user = self.organization.get_user_authorization(self.user)
        authorization_user.role = OrganizationAuthorization.ROLE_CONTRIBUTOR
        authorization_user.save()
        self.assertTrue(authorization_user.can_contribute)

        # private organization
        authorization_user = self.organization.get_user_authorization(self.user)
        authorization_user.role = OrganizationAuthorization.ROLE_CONTRIBUTOR
        authorization_user.save()
        self.assertTrue(authorization_user.can_contribute)


class UtilsTestCase(TestCase):
    def setUp(self):
        self.precification = GenericBillingData.get_generic_billing_data_instance()

    def test_calculate_active_contacts(self):
        self.assertEqual(self.precification.calculate_active_contacts(contact_count=0), 267.0)
        self.assertEqual(self.precification.calculate_active_contacts(contact_count=999), 267.0)
        self.assertEqual(self.precification.calculate_active_contacts(contact_count=1000), 267.0)
        self.assertEqual(self.precification.calculate_active_contacts(contact_count=9999), 1669.833)
        self.assertEqual(self.precification.calculate_active_contacts(contact_count=10000), 1670.0)
        self.assertEqual(
            self.precification.calculate_active_contacts(contact_count=29999), 4679.844
        )
        self.assertEqual(self.precification.calculate_active_contacts(contact_count=30000), 4680.0)
        self.assertEqual(self.precification.calculate_active_contacts(contact_count=49999), 7199.856)
        self.assertEqual(
            self.precification.calculate_active_contacts(contact_count=50000), 7199.999999999999
        )
        self.assertEqual(self.precification.calculate_active_contacts(contact_count=999999), 132999.867)
        self.assertEqual(
            self.precification.calculate_active_contacts(contact_count=100000), 14000.000000000002
        )
        self.assertEqual(self.precification.calculate_active_contacts(contact_count=249999), 33249.867)
        self.assertEqual(self.precification.calculate_active_contacts(contact_count=250000), 33250.0)


class InvoiceTestCase(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="Test Invoice without Invoice project", inteligence_organization=0,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="enterprise",
        )
        self.invoice = self.organization.organization_billing_invoice.create(
            due_date=timezone.now() + timedelta(days=30),
            invoice_random_id=1
            if self.organization.organization_billing_invoice.last() is None else self.organization.organization_billing_invoice.last().invoice_random_id + 1,
            discount=self.organization.organization_billing.fixed_discount,
            extra_integration=self.organization.extra_integration,
            cost_per_whatsapp=settings.BILLING_COST_PER_WHATSAPP,
        )

        self.generic_billing_data = GenericBillingData.get_generic_billing_data_instance()

    def test_if_invoice_project_null(self):
        self.assertTrue(not self.invoice.organization_billing_invoice_project.all())
        self.assertEqual(float(self.invoice.total_invoice_amount), float(self.generic_billing_data.calculate_active_contacts(self.organization.active_contacts)))
