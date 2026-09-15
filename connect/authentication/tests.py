import unittest
from django.test import TestCase, override_settings
from django.db import IntegrityError
from unittest.mock import patch

from .models import User


@unittest.skip("Test broken, need to configure rabbitmq")
class AuthenticationTestCase(TestCase):
    def test_new_user(self):
        User.objects.create_user("fake@user.com", "fake")

    def test_new_superuser(self):
        User.objects.create_superuser("fake@user.com", "fake")

    def test_new_user_fail_without_email(self):
        with self.assertRaises(ValueError):
            User.objects._create_user("", "fake")

    def test_new_user_fail_without_nickname(self):
        with self.assertRaises(ValueError):
            User.objects._create_user("fake@user.com", "")

    def test_new_superuser_fail_issuperuser_false(self):
        with self.assertRaises(ValueError):
            User.objects.create_superuser("fake@user.com", "fake", is_superuser=False)

    def test_user_unique_nickname(self):
        User.objects.create_user("user1@user.com", "fake")
        with self.assertRaises(IntegrityError):
            User.objects.create_user("user2@user.com", "fake")


@unittest.skip("Test broken, need to configure rabbitmq")
class UserTestCase(TestCase):
    def setUp(self):

        self.user = User.objects.create_user(
            username="fake",
            email="fake@fake.com",
            first_name="Fake",
            last_name="User",
            language="en",
        )

    @patch(
        "connect.api.v1.internal.chats.chats_rest_client.ChatsRESTClient.update_user_language"
    )
    @patch(
        "connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.update_language"
    )
    @patch(
        "connect.api.v1.internal.intelligence.intelligence_rest_client.IntelligenceRESTClient.update_language"
    )
    @patch(
        "connect.api.v1.internal.insights.insights_rest_client.InsightsRESTClient.update_user_language"
    )
    def test_update_language(
        self,
        insights_update_user_language,
        intel_update_language,
        flows_update_language,
        chats_update_user_language,
    ):
        chats_update_user_language.return_value = True
        flows_update_language.return_value = True
        intel_update_language.return_value = True
        insights_update_user_language.return_value = True
        self.user.update_language("pt_br")
        self.assertEqual(self.user.language, "pt_br")

    def test_token_generator(self):
        self.assertTrue(self.user.token_generator)

    @override_settings(SEND_EMAIL=False)
    def test_send_email_false_change_password_email(self):
        self.assertFalse(self.user.send_change_password_email())

    @patch("connect.api.v1.keycloak.KeycloakControl.get_instance")
    @patch("connect.api.v1.keycloak.KeycloakControl.set_verify_email")
    def test_set_verify_email(self, mock_set_verify_email, mock_get_instance):

        self.user.set_verify_email()
        self.assertFalse(self.user.first_login)


@override_settings(USE_EDA_PERMISSIONS=False)
class UserManagerValidationTestCase(TestCase):
    def test_create_user_requires_email(self):
        with self.assertRaises(ValueError):
            User.objects._create_user("", "fake")

    def test_create_user_requires_username(self):
        with self.assertRaises(ValueError):
            User.objects._create_user("fake@user.com", "")

    def test_create_superuser_requires_is_superuser(self):
        with self.assertRaises(ValueError):
            User.objects.create_superuser(
                "fake@user.com", "fake", is_superuser=False
            )


@override_settings(USE_EDA_PERMISSIONS=False, SEND_EMAILS=False)
class UserHelperTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "helper@user.com",
            "helper_user",
            first_name="Helper",
            language="en",
        )

    def test_token_generator(self):
        self.assertTrue(self.user.token_generator)

    def test_other_positions_and_photo_url(self):
        self.user.position = "other:contractor"
        self.assertEqual(self.user.other_positions, "contractor")
        self.user.position = "engineer"
        self.assertIsNone(self.user.other_positions)
        self.assertIsNone(self.user.photo_url)

    def test_get_company_data(self):
        data = self.user.get_company_data
        self.assertEqual(
            set(data),
            {
                "company_name",
                "company_segment",
                "company_sector",
                "number_people",
                "weni_helps",
            },
        )

    def test_save_first_login_token(self):
        self.user.save_first_login_token("token-value")
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_login_token, "token-value")

    def test_send_email_access_password_when_emails_disabled(self):
        self.assertFalse(self.user.send_email_access_password("secret"))

    def test_check_password_reset_token_rejects_invalid_token(self):
        self.assertFalse(self.user.check_password_reset_token("not-a-token"))

    @patch(
        "connect.api.v1.internal.chats.chats_rest_client.ChatsRESTClient.update_user_language"
    )
    @patch(
        "connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.update_language"
    )
    @patch(
        "connect.api.v1.internal.intelligence.intelligence_rest_client.IntelligenceRESTClient.update_language"
    )
    @patch(
        "connect.api.v1.internal.insights.insights_rest_client.InsightsRESTClient.update_user_language"
    )
    def test_update_language(
        self,
        insights_update_user_language,
        intel_update_language,
        flows_update_language,
        chats_update_user_language,
    ):
        chats_update_user_language.return_value = True
        flows_update_language.return_value = True
        intel_update_language.return_value = True
        insights_update_user_language.return_value = True
        self.user.update_language("pt_br")
        self.assertEqual(self.user.language, "pt_br")
