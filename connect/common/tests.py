import uuid as uuid4

from django.test import TestCase

from connect.authentication.models import User
from connect.common.models import (
    Newsletter,
    ProjectRole,
    Service,
    Organization,
    ServiceStatus,
    NewsletterLanguage,
    BillingPlan,
    GenericBillingData,
    RequestPermissionProject,
    OrganizationRole,
    OrganizationLevelRole,
    ProjectRoleLevel,
    RocketRole,
    RocketRoleLevel,
    RocketAuthorization,
    ProjectRoleLevel,
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
        self.assertEqual(
            newsletter_language.__str__(),
            f"Newsletter PK: {newsletter_language.pk} - en-us - New feature",
        )
        self.assertEqual(newsletter.__str__(), f"PK: {newsletter.pk}")
        self.assertEqual(newsletter_language.title, title)
        self.assertEqual(newsletter_language.description, description)


class ServiceStatusTestCase(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner@user.com", "owner")

        self.organization = Organization.objects.create(
            name="Test",
            inteligence_organization=0,
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
        self.financial = User.objects.create_user("financial@user.com", "financial")
        self.contributor = User.objects.create_user("contrib@user.com", "contrib")

        self.organization = Organization.objects.create(
            name="Test",
            inteligence_organization=0,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="free",
        )
        self.organization_authorization = self.organization.authorizations.create(
            user=self.owner, role=OrganizationRole.ADMIN.value
        )
        self.organization_financial_authorization = (
            self.organization.authorizations.create(
                user=self.financial, role=OrganizationRole.FINANCIAL.value
            )
        )

        self.organization_contribute_authorization = (
            self.organization.authorizations.create(
                user=self.contributor, role=OrganizationRole.CONTRIBUTOR.value
            )
        )

    def test_admin_level(self):
        authorization = self.organization.get_user_authorization(self.owner)
        self.assertEqual(authorization.level, OrganizationLevelRole.ADMIN.value)

    def test_not_read_level(self):
        authorization = self.organization.get_user_authorization(self.user)
        self.assertNotEqual(
            authorization.level, OrganizationLevelRole.CONTRIBUTOR.value
        )

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
        authorization_user.role = OrganizationRole.CONTRIBUTOR.value
        authorization_user.save()
        self.assertTrue(authorization_user.can_read)

        # private organization
        authorization_user = self.organization.get_user_authorization(self.user)
        authorization_user.role = OrganizationRole.CONTRIBUTOR.value
        authorization_user.save()
        self.assertTrue(authorization_user.can_read)

    # All users now are contributors, they can create projects
    # on the organization but only read and write in those which they have permissions

    # def test_role_user_can_t_contribute(self):
    #     # public organization
    #     authorization_user = self.organization.get_user_authorization(self.user)
    #     authorization_user.role = OrganizationRole.VIEWER.value
    #     authorization_user.save()
    #     self.assertFalse(authorization_user.can_contribute)

    # # private organization
    # authorization_user = self.organization.get_user_authorization(self.user)
    # authorization_user.role = OrganizationRole.VIEWER.value
    # authorization_user.save()
    # self.assertFalse(authorization_user.can_contribute)

    def test_role_contributor_can_contribute(self):
        # public organization
        authorization_user = self.organization.get_user_authorization(self.user)
        authorization_user.role = OrganizationRole.CONTRIBUTOR.value
        authorization_user.save()
        self.assertTrue(authorization_user.can_contribute)

        # private organization
        authorization_user = self.organization.get_user_authorization(self.user)
        authorization_user.role = OrganizationRole.CONTRIBUTOR.value
        authorization_user.save()
        self.assertTrue(authorization_user.can_contribute)

    def test_str_organization_authorization(self):
        self.assertEqual(
            "Test - owner@user.com", self.organization_authorization.__str__()
        )

    def test_financial_level(self):
        self.assertTrue(self.organization_financial_authorization.is_financial)

    def test_can_contribute_billing(self):
        self.assertTrue(
            self.organization_financial_authorization.can_contribute_billing
        )
        self.assertTrue(self.organization_authorization.can_contribute_billing)
        self.assertFalse(
            self.organization_contribute_authorization.can_contribute_billing
        )


class UtilsTestCase(TestCase):
    def setUp(self):
        self.precification = GenericBillingData.get_generic_billing_data_instance()

    def test_calculate_active_contacts(self):
        self.assertEqual(
            self.precification.calculate_active_contacts(contact_count=0), 267.0
        )
        self.assertEqual(
            self.precification.calculate_active_contacts(contact_count=999), 267.0
        )
        self.assertEqual(
            self.precification.calculate_active_contacts(contact_count=1000), 267.0
        )
        self.assertEqual(
            self.precification.calculate_active_contacts(contact_count=9999), 1669.833
        )
        self.assertEqual(
            self.precification.calculate_active_contacts(contact_count=10000), 1670.0
        )
        self.assertEqual(
            self.precification.calculate_active_contacts(contact_count=29999), 4679.844
        )
        self.assertEqual(
            self.precification.calculate_active_contacts(contact_count=30000), 4680.0
        )
        self.assertEqual(
            self.precification.calculate_active_contacts(contact_count=49999), 7199.856
        )
        self.assertEqual(
            self.precification.calculate_active_contacts(contact_count=50000),
            7199.999999999999,
        )
        self.assertEqual(
            self.precification.calculate_active_contacts(contact_count=999999),
            132999.867,
        )
        self.assertEqual(
            self.precification.calculate_active_contacts(contact_count=100000),
            14000.000000000002,
        )
        self.assertEqual(
            self.precification.calculate_active_contacts(contact_count=249999),
            33249.867,
        )
        self.assertEqual(
            self.precification.calculate_active_contacts(contact_count=250000), 33250.0
        )

    def test_str_generic_billing_data(self):
        self.assertEqual(
            self.precification.__str__(),
            f"{self.precification.free_active_contacts_limit}",
        )


class InvoiceTestCase(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="Test Invoice without Invoice project",
            inteligence_organization=0,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="enterprise",
        )
        self.invoice = self.organization.organization_billing_invoice.create(
            due_date=timezone.now() + timedelta(days=30),
            invoice_random_id=1
            if self.organization.organization_billing_invoice.last() is None
            else self.organization.organization_billing_invoice.last().invoice_random_id
            + 1,
            discount=self.organization.organization_billing.fixed_discount,
            extra_integration=self.organization.extra_integration,
            cost_per_whatsapp=settings.BILLING_COST_PER_WHATSAPP,
        )

        self.generic_billing_data = (
            GenericBillingData.get_generic_billing_data_instance()
        )

    def test_if_invoice_project_null(self):
        self.assertTrue(not self.invoice.organization_billing_invoice_project.all())
        self.assertEqual(
            float(self.invoice.total_invoice_amount),
            float(
                self.generic_billing_data.calculate_active_contacts(
                    self.organization.active_contacts
                )
            ),
        )


class OrganizationTestCase(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="Test Organization",
            inteligence_organization=0,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="enterprise",
        )
        self.test_email = "test@example.com"
        self.test_user_name = "test_username"
        self.test_first_name = "test"
        self.organization_new_name = "Test Org"

    def test_str_organization(self):
        self.assertEqual(
            self.organization.__str__(),
            f"{self.organization.uuid} - {self.organization.name}",
        )

    def test_send_email_invite_organization(self):
        sended_mail = self.organization.send_email_invite_organization(
            email=self.test_email
        )
        self.assertEqual(len(sended_mail.outbox), 1)
        outbox = sended_mail.outbox[0]
        self.assertEqual(outbox.subject, "Invitation to join organization")
        self.assertEqual(outbox.from_email, settings.DEFAULT_FROM_EMAIL)
        self.assertEqual(outbox.to[0], self.test_email)

    def test_send_email_organization_going_out(self):
        sended_mail = self.organization.send_email_organization_going_out(
            self.test_user_name, self.test_email
        )
        self.assertEqual(len(sended_mail.outbox), 1)
        outbox = sended_mail.outbox[0]
        self.assertEqual(
            outbox.subject, f"You are going out of {self.organization.name}"
        )
        self.assertEqual(outbox.from_email, settings.DEFAULT_FROM_EMAIL)
        self.assertEqual(outbox.to[0], self.test_email)

    def test_send_email_organization_removed(self):
        sended_mail = self.organization.send_email_organization_removed(
            self.test_email, self.test_user_name
        )
        self.assertEqual(len(sended_mail.outbox), 1)
        outbox = sended_mail.outbox[0]
        self.assertEqual(
            outbox.subject, f"You have been removed from {self.organization.name}"
        )
        self.assertEqual(outbox.from_email, settings.DEFAULT_FROM_EMAIL)
        self.assertEqual(outbox.to[0], self.test_email)

    def test_send_email_organization_create(self):
        sended_mail = self.organization.send_email_organization_create(
            self.test_email, self.test_first_name
        )
        self.assertEqual(len(sended_mail.outbox), 1)
        outbox = sended_mail.outbox[0]
        self.assertEqual(outbox.subject, "Organization created!")
        self.assertEqual(outbox.from_email, settings.DEFAULT_FROM_EMAIL)
        self.assertEqual(outbox.to[0], self.test_email)

    def test_send_email_remove_permission_organization(self):
        sended_mail = self.organization.send_email_remove_permission_organization(
            self.test_first_name, self.test_email
        )
        self.assertEqual(len(sended_mail.outbox), 1)
        outbox = sended_mail.outbox[0]
        self.assertEqual(
            outbox.subject, f"You have been removed from the {self.organization.name}"
        )
        self.assertEqual(outbox.from_email, settings.DEFAULT_FROM_EMAIL)
        self.assertEqual(outbox.to[0], self.test_email)

    def test_send_email_delete_organization(self):
        sended_email = self.organization.send_email_delete_organization(
            self.test_first_name, self.test_email
        )
        self.assertEqual(len(sended_email.outbox), 1)
        outbox = sended_email.outbox[0]
        self.assertEqual(outbox.subject, f"{self.organization.name} no longer exists!")
        self.assertEqual(outbox.from_email, settings.DEFAULT_FROM_EMAIL)
        self.assertEqual(outbox.to[0], self.test_email)

    def test_send_email_change_organization_name(self):
        sended_email = self.organization.send_email_change_organization_name(
            self.test_user_name,
            self.test_email,
            self.organization.name,
            self.organization_new_name,
        )
        self.assertEqual(len(sended_email.outbox), 1)
        outbox = sended_email.outbox[0]
        self.assertEqual(
            outbox.subject,
            f"{self.organization.name} now it's {self.organization_new_name}",
        )
        self.assertEqual(outbox.from_email, settings.DEFAULT_FROM_EMAIL)
        self.assertEqual(outbox.to[0], self.test_email)

    def test_send_email_access_code(self):
        sended_email = self.organization.send_email_access_code(
            self.test_email, self.test_user_name, "1234"
        )
        self.assertEqual(len(sended_email.outbox), 1)
        outbox = sended_email.outbox[0]
        self.assertEqual(outbox.subject, "You receive an access code to Weni Platform")
        self.assertEqual(outbox.from_email, settings.DEFAULT_FROM_EMAIL)
        self.assertEqual(outbox.to[0], self.test_email)

    def test_send_email_permission_change(self):
        sended_email = self.organization.send_email_permission_change(
            self.test_user_name, "Admin", "Viewer", self.test_email
        )
        self.assertEqual(len(sended_email.outbox), 1)
        outbox = sended_email.outbox[0]
        self.assertEqual(outbox.subject, "A new permission has been assigned to you")
        self.assertEqual(outbox.from_email, settings.DEFAULT_FROM_EMAIL)
        self.assertEqual(outbox.to[0], self.test_email)


class BillingPlanTestCase(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="Test",
            inteligence_organization=0,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="free",
        )
        self.billing = self.organization.organization_billing
        self.test_user_name = "test username"
        self.test_email = ["test@example.com"]
        self.test_first_name = "test"
        # self.organization.organization_billing.stripe_customer="cus_KpDZ129lPQbygj"
        # self.organization.organization_billing.save()

    def test_send_email_added_card(self):
        sended_email = self.billing.send_email_added_card(
            self.test_user_name, self.test_email
        )
        self.assertEqual(len(sended_email.outbox), 1)
        outbox = sended_email.outbox[0]
        self.assertEqual(
            outbox.subject,
            f"A credit card has been added to the organization {self.organization.name}",
        )
        self.assertEqual(outbox.from_email, settings.DEFAULT_FROM_EMAIL)
        self.assertEqual(outbox.to[0], self.test_email[0])

    def test_send_email_changed_card(self):
        sended_email = self.billing.send_email_changed_card(
            self.test_user_name, self.test_email
        )
        self.assertEqual(len(sended_email.outbox), 1)
        outbox = sended_email.outbox[0]
        self.assertEqual(
            outbox.subject,
            f"A credit card has been changed to the organization {self.organization.name}",
        )
        self.assertEqual(outbox.from_email, settings.DEFAULT_FROM_EMAIL)
        self.assertEqual(outbox.to[0], self.test_email[0])

    def test_send_email_finished_plan(self):
        sended_email = self.billing.send_email_finished_plan(
            self.test_user_name, self.test_email
        )
        self.assertEqual(len(sended_email.outbox), 1)
        outbox = sended_email.outbox[0]
        self.assertEqual(
            outbox.subject,
            f"Your {self.organization.name} organization's plan has ended",
        )
        self.assertEqual(outbox.from_email, settings.DEFAULT_FROM_EMAIL)
        self.assertEqual(outbox.to[0], self.test_email[0])

    def test_send_email_reactivated_plan(self):
        sended_email = self.billing.send_email_reactivated_plan(
            self.test_user_name, self.test_email
        )
        self.assertEqual(len(sended_email.outbox), 1)
        outbox = sended_email.outbox[0]
        self.assertEqual(
            outbox.subject,
            f"Your {self.organization.name} organization's plan has been reactivated.",
        )
        self.assertEqual(outbox.from_email, settings.DEFAULT_FROM_EMAIL)
        self.assertEqual(outbox.to[0], self.test_email[0])

    def test_send_email_removed_credit_card(self):
        sended_email = self.billing.send_email_removed_credit_card(
            self.test_user_name, self.test_email
        )
        self.assertEqual(len(sended_email.outbox), 1)
        outbox = sended_email.outbox[0]
        self.assertEqual(
            outbox.subject,
            f"Your {self.organization.name} organization credit card was removed",
        )
        self.assertEqual(outbox.from_email, settings.DEFAULT_FROM_EMAIL)
        self.assertEqual(outbox.to[0], self.test_email[0])

    def test_send_email_expired_free_plan(self):
        sended_email = self.billing.send_email_expired_free_plan(
            self.test_user_name, self.test_email
        )
        self.assertEqual(len(sended_email.outbox), 1)
        outbox = sended_email.outbox[0]
        self.assertEqual(
            outbox.subject,
            f"The organization {self.organization.name} has already surpassed 200 active contacts",
        )
        self.assertEqual(outbox.from_email, settings.DEFAULT_FROM_EMAIL)
        self.assertEqual(outbox.to[0], self.test_email[0])

    def test_send_email_chosen_plan(self):
        plan = BillingPlan.PLAN_ENTERPRISE
        sended_email = self.billing.send_email_chosen_plan(
            self.test_user_name, self.test_email[0], plan
        )
        self.assertEqual(len(sended_email.outbox), 1)
        outbox = sended_email.outbox[0]
        self.assertEqual(
            outbox.subject,
            f"Your {self.organization.name} organization has the {plan.title()} Plan",
        )
        self.assertEqual(outbox.from_email, settings.DEFAULT_FROM_EMAIL)
        self.assertEqual(outbox.to[0], self.test_email[0])

    def test_send_email_changed_plan(self):
        plan = BillingPlan.PLAN_CHOICES[1][0]
        sended_email = self.billing.send_email_changed_plan(
            self.test_user_name, self.test_email, plan
        )
        self.assertEqual(len(sended_email.outbox), 1)
        outbox = sended_email.outbox[0]
        self.assertEqual(
            outbox.subject,
            f"Your {self.organization.name} organization's plan has been changed.",
        )
        self.assertEqual(outbox.from_email, settings.DEFAULT_FROM_EMAIL)
        self.assertEqual(outbox.to[0], self.test_email[0])


class ProjectAuthorizationTestCase(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner@user.com", "owner")
        self.user = User.objects.create_user("fake@user.com", "user")

        self.organization = Organization.objects.create(
            name="Test",
            inteligence_organization=0,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="free",
        )
        self.organization_authorization = self.organization.authorizations.create(
            user=self.owner, role=OrganizationRole.ADMIN.value
        )
        self.project = self.organization.project.create(
            name="project test",
            timezone="America/Sao_Paulo",
            flow_organization=uuid4.uuid4(),
        )
        self.project_authorization = self.project.project_authorizations.create(
            user=self.owner,
            role=ProjectRoleLevel.MODERATOR.value,
            organization_authorization=self.organization_authorization,
        )

    def test_admin_level(self):
        authorization = self.project.get_user_authorization(self.owner)
        self.assertEqual(authorization.level, ProjectRoleLevel.MODERATOR.value)

    def test_not_read_level(self):
        authorization = self.project.get_user_authorization(self.user)
        self.assertNotEqual(authorization.level, ProjectRoleLevel.CONTRIBUTOR.value)

    def test_can_read(self):
        # project owner
        authorization_owner = self.project.get_user_authorization(self.owner)
        self.assertTrue(authorization_owner.can_read)
        # secondary user
        private_authorization_user = self.project.get_user_authorization(self.user)
        self.assertFalse(private_authorization_user.can_read)

    def test_can_contribute(self):
        # organization owner
        authorization_owner = self.project.get_user_authorization(self.owner)
        self.assertTrue(authorization_owner.can_contribute)
        # secondary user
        authorization_user = self.project.get_user_authorization(self.user)
        self.assertFalse(authorization_user.can_contribute)

        private_authorization_owner = self.project.get_user_authorization(self.owner)
        self.assertTrue(private_authorization_owner.can_contribute)
        # secondary user
        private_authorization_user = self.project.get_user_authorization(self.user)
        self.assertFalse(private_authorization_user.can_contribute)

    def test_can_write(self):
        # organization owner
        authorization_owner = self.project.get_user_authorization(self.owner)
        self.assertTrue(authorization_owner.can_write)
        # secondary user
        authorization_user = self.project.get_user_authorization(self.user)
        self.assertFalse(authorization_user.can_write)
        # private owner
        private_authorization_owner = self.project.get_user_authorization(self.owner)
        self.assertTrue(private_authorization_owner.can_write)
        # secondary user
        private_authorization_user = self.project.get_user_authorization(self.user)
        self.assertFalse(private_authorization_user.can_write)

    def test_is_moderator(self):
        # organization owner
        authorization_owner = self.project.project_authorizations.get(user=self.owner)
        self.assertTrue(authorization_owner.is_moderator)
        # secondary user
        authorization_user = self.project.get_user_authorization(self.user)
        self.assertFalse(authorization_user.is_moderator)
        # private owner
        private_authorization_owner = self.project.get_user_authorization(
            self.owner
        )
        self.assertTrue(private_authorization_owner.is_moderator)
        # secondary user
        private_authorization_user = self.project.get_user_authorization(self.user)
        self.assertFalse(private_authorization_user.is_moderator)

    def test_owner_ever_admin(self):
        authorization_owner = self.project.project_authorizations.get(user=self.owner)
        self.assertTrue(authorization_owner.is_moderator)


class RocketAuthorizationTestCase(TestCase):
    def setUp(self):
        self.agent_authorization = RocketAuthorization.objects.create(role=RocketRole.AGENT.value)
        self.service_manager_authorization = RocketAuthorization.objects.create(role=RocketRole.SERVICE_MANAGER.value)
        self.not_set_auth = RocketAuthorization.objects.create()

    def test_level_agent(self):
        self.assertTrue(self.agent_authorization.level == RocketRoleLevel.AGENT.value)
        self.assertFalse(self.agent_authorization.level == RocketRoleLevel.SERVICE_MANAGER.value)

    def test_level_service_manager(self):
        self.assertTrue(self.service_manager_authorization.level == RocketRoleLevel.SERVICE_MANAGER.value)
        self.assertFalse(self.service_manager_authorization.level == RocketRoleLevel.AGENT.value)

    def test_level_nothing_permission(self):
        self.assertTrue(self.not_set_auth.level == RocketRoleLevel.NOTHING.value)


class RequestPermissionProjectTestCase(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner@user.com", "owner")
        self.user = User.objects.create_user("fake@user.com", "user")

        self.organization = Organization.objects.create(
            name="Test",
            inteligence_organization=0,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="free",
        )
        self.organization_authorization = self.organization.authorizations.create(
            user=self.owner, role=OrganizationRole.ADMIN.value
        )
        self.project = self.organization.project.create(
            name="project test",
            timezone="America/Sao_Paulo",
            flow_organization=uuid4.uuid4(),
        )

    def test_create_request_permission(self):
        self.request_permission = RequestPermissionProject.objects.create(
            email="fake@user.com",
            project=self.project,
            role=ProjectRole.ADMIN.value,
            created_by=self.owner,
        )
        self.assertTrue(self.request_permission)
        self.assertEqual(
            self.request_permission.__str__(),
            f"{self.request_permission.project.name}, {self.request_permission.role}, <{self.request_permission.email}>",
        )
