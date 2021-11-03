import uuid as uuid4

from django.test import TestCase

from connect import utils
from connect.authentication.models import User
from connect.common.models import (
    Newsletter,
    Service,
    Organization,
    OrganizationAuthorization,
    ServiceStatus,
    NewsletterLanguage,
)


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
            name="Test", inteligence_organization=0
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
            name="Test", inteligence_organization=0
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
    def test_calculate_active_contacts(self):
        self.assertEqual(utils.calculate_active_contacts(value=0), 267.0)
        self.assertEqual(utils.calculate_active_contacts(value=999), 267.0)
        self.assertEqual(utils.calculate_active_contacts(value=1000), 267.0)
        self.assertEqual(utils.calculate_active_contacts(value=9999), 1779.822)
        self.assertEqual(utils.calculate_active_contacts(value=10000), 1670.0)
        self.assertEqual(
            utils.calculate_active_contacts(value=29999), 5009.8330000000005
        )
        self.assertEqual(utils.calculate_active_contacts(value=30000), 4680.0)
        self.assertEqual(utils.calculate_active_contacts(value=49999), 7799.844)
        self.assertEqual(
            utils.calculate_active_contacts(value=50000), 7199.999999999999
        )
        self.assertEqual(utils.calculate_active_contacts(value=999999), 132999.867)
        self.assertEqual(
            utils.calculate_active_contacts(value=100000), 14000.000000000002
        )
        self.assertEqual(utils.calculate_active_contacts(value=249999), 34999.86)
        self.assertEqual(utils.calculate_active_contacts(value=249999), 34999.86)
        self.assertEqual(utils.calculate_active_contacts(value=250000), 33250.0)
