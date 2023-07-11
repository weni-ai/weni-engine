from django.test import TestCase, override_settings
from django.db import IntegrityError
from unittest.mock import patch

from .models import User


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


class UserTestCase(TestCase):

    def setUp(self):

        self.user = User.objects.create_user(
            username="fake",
            email="fake@fake.com",
            first_name="Fake",
            last_name="User",
            language="en"
        )

    @patch("connect.api.v1.internal.chats.chats_rest_client.ChatsRESTClient.update_user_language")
    @patch("connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.update_language")
    @patch("connect.api.v1.internal.intelligence.intelligence_rest_client.IntelligenceRESTClient.update_language")
    def test_update_language(self, chats_update_user_language, flows_update_language, intel_update_language):
        chats_update_user_language.return_value = True
        flows_update_language.return_value = True
        intel_update_language.return_value = True
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
