"""Tests for NotifyBusinessVerificationUseCase."""

from unittest.mock import patch

from django.test import TestCase, override_settings

from connect.authentication.models import User
from connect.usecases.business_verification.notify_business_verification import (
    APPROVED_STATUS,
    DEFAULT_SUPPORT_URL,
    FAILED_STATUS,
    TEMPLATE_HTML,
    TEMPLATE_TXT,
    NotifyBusinessVerificationUseCase,
)


@override_settings(SEND_EMAILS=True, DEFAULT_LANGUAGE="en-us")
class NotifyBusinessVerificationUseCaseTestCase(TestCase):
    def setUp(self):
        self.use_case = NotifyBusinessVerificationUseCase()
        self.user = User.objects.create(
            email="customer@example.com",
            username="customer",
            first_name="Alice",
            language="pt-br",
        )

    @patch("connect.usecases.business_verification.notify_business_verification.send_email")
    def test_sends_approved_email(self, mock_send):
        result = self.use_case.execute(
            user_email=self.user.email,
            status=APPROVED_STATUS,
            verification_attempts=1,
        )

        self.assertTrue(result)
        mock_send.assert_called_once()
        kwargs = mock_send.call_args.kwargs
        self.assertEqual(kwargs["to"], self.user.email)
        self.assertEqual(kwargs["template_txt"], TEMPLATE_TXT)
        self.assertEqual(kwargs["template_html"], TEMPLATE_HTML)
        self.assertTrue(kwargs["context"]["is_approved"])
        self.assertEqual(kwargs["context"]["support_url"], DEFAULT_SUPPORT_URL)

    @patch("connect.usecases.business_verification.notify_business_verification.send_email")
    def test_sends_failed_email(self, mock_send):
        self.use_case.execute(
            user_email=self.user.email,
            status=FAILED_STATUS,
            rejection_reasons=["LEGAL_NAME_NOT_FOUND_IN_DOCUMENTS"],
            verification_attempts=1,
        )

        context = mock_send.call_args.kwargs["context"]
        self.assertFalse(context["is_approved"])
        self.assertIn("support_url", context)

    @override_settings(BUSINESS_VERIFICATION_SUPPORT_URL="https://custom.support/contact")
    @patch("connect.usecases.business_verification.notify_business_verification.send_email")
    def test_uses_custom_support_url_from_settings(self, mock_send):
        self.use_case.execute(
            user_email=self.user.email,
            status=FAILED_STATUS,
        )
        context = mock_send.call_args.kwargs["context"]
        self.assertEqual(context["support_url"], "https://custom.support/contact")

    @patch("connect.usecases.business_verification.notify_business_verification.send_email")
    def test_explicit_language_overrides_user_language(self, mock_send):
        self.use_case.execute(
            user_email=self.user.email,
            status=APPROVED_STATUS,
            language="es",
        )
        mock_send.assert_called_once()

    @patch("connect.usecases.business_verification.notify_business_verification.send_email")
    def test_unknown_user_still_dispatches(self, mock_send):
        result = self.use_case.execute(
            user_email="unknown@example.com",
            status=APPROVED_STATUS,
        )
        self.assertTrue(result)
        kwargs = mock_send.call_args.kwargs
        self.assertEqual(kwargs["to"], "unknown@example.com")

    @override_settings(SEND_EMAILS=False)
    @patch("connect.usecases.business_verification.notify_business_verification.send_email")
    def test_skips_when_send_emails_disabled(self, mock_send):
        result = self.use_case.execute(
            user_email=self.user.email,
            status=APPROVED_STATUS,
        )
        self.assertFalse(result)
        mock_send.assert_not_called()
