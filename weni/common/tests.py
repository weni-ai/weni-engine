from django.test import TestCase

from weni.common.models import Newsletter, Service


class NewsletterTestCase(TestCase):
    def test_newsletter_create(self):
        title = "New feature"
        description = "test description"
        newsletter = Newsletter.objects.create(title=title, description=description)
        self.assertEqual(newsletter.title, title)
        self.assertEqual(newsletter.description, description)


class ServiceStatusTestCase(TestCase):
    def setUp(self):
        self.service = Service.objects.create(
            url="http://test.com", status=False, default=False
        )

    # def test_create_service_status(self):
    #     user = User.objects.create_user("fake@user.com", "user", "123456")
    #     status = ServiceStatus.objects.create(
    #         service=self.service,
    #         user=user,
    #     )
    #     self.assertEqual(status.service.url, "http://test.com")
    #     self.assertEqual(status.service.status, False)
    #     self.assertEqual(status.service.default, False)

    # def test_create_service_default(self):
    #     service = Service.objects.create(
    #         url="http://test-default.com", status=True, default=True
    #     )
    #     user = User.objects.create_user("fake@user.com", "user", "123456")
    #     self.assertEqual(user.service_status.all().first().service.url, service.url)
    #     self.assertEqual(
    #         user.service_status.all().first().service.status, service.status
    #     )
    #     self.assertEqual(
    #         user.service_status.all().first().service.default, service.default
    #     )
