import uuid as uuid4

from django.test import TestCase

from weni.authentication.models import User
from weni.common.models import (
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
        newsletter_language = NewsletterLanguage.objects.create(
            title=title, description=description
        )
        newsletter = Newsletter.objects.create(newsletter_language=newsletter_language)
        self.assertEqual(newsletter.newsletter_language.title, title)
        self.assertEqual(newsletter.newsletter_language.description, description)
        self.assertEqual(str(newsletter), newsletter.newsletter_language.title)


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
