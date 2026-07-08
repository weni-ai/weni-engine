"""Tests for email helpers in connect.common.utils."""

from django.core import mail
from django.test import TestCase, override_settings

from connect.common.utils import send_html_email


@override_settings(
    SEND_EMAILS=True,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    SENDGRID_UNSUBSCRIBE_GROUP_ID=None,
)
class SendHtmlEmailTestCase(TestCase):
    def setUp(self):
        mail.outbox = []

    def test_sends_html_body_as_alternative_with_attachment(self):
        send_html_email(
            subject="Your Weni contract",
            to="customer@example.com",
            html_content="<p>Contract accepted</p>",
            attachments=[("contract.pdf", b"%PDF-1.4 fake", "application/pdf")],
        )

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.subject, "Your Weni contract")
        self.assertEqual(message.to, ["customer@example.com"])
        self.assertEqual(message.body, "Contract accepted")
        self.assertEqual(
            message.alternatives, [("<p>Contract accepted</p>", "text/html")]
        )

        filename, content, mimetype = message.attachments[0]
        self.assertEqual(filename, "contract.pdf")
        self.assertEqual(content, b"%PDF-1.4 fake")
        self.assertEqual(mimetype, "application/pdf")

    def test_uses_explicit_text_content_when_provided(self):
        send_html_email(
            subject="Your Weni contract",
            to="customer@example.com",
            html_content="<p>Contract accepted</p>",
            text_content="Plain fallback",
        )

        self.assertEqual(mail.outbox[0].body, "Plain fallback")

    @override_settings(SEND_EMAILS=False)
    def test_skips_when_send_emails_disabled(self):
        send_html_email(
            subject="Your Weni contract",
            to="customer@example.com",
            html_content="<p>Contract accepted</p>",
        )

        self.assertEqual(len(mail.outbox), 0)
