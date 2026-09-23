"""Tests for SendContractAcceptanceEmailUseCase."""

import base64
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings

from connect.usecases.commerce.dto import SendContractAcceptanceEmailDTO
from connect.usecases.commerce.send_contract_acceptance_email import (
    PDF_MIME_TYPE,
    SendContractAcceptanceEmailUseCase,
)


PDF_BYTES = b"%PDF-1.4 fake-contract-content"
PDF_BASE64 = base64.b64encode(PDF_BYTES).decode()
ACCEPTED_AT = datetime(2026, 6, 10, 14, 32, tzinfo=timezone.utc)
LOGO_URL = "https://weni-media-sp.s3-sa-east-1.amazonaws.com/logo/Logo.png"


def _dto(**overrides) -> SendContractAcceptanceEmailDTO:
    defaults = dict(
        user_email="customer@example.com",
        acceptance_id=uuid.uuid4(),
        language="pt-br",
        plan_name="Growth",
        contract_version="v2.1",
        accepted_at=ACCEPTED_AT,
        file_name="contract-v2.1.pdf",
        file_base64=PDF_BASE64,
    )
    defaults.update(overrides)
    return SendContractAcceptanceEmailDTO(**defaults)


@override_settings(
    SEND_EMAILS=True,
    DEFAULT_LANGUAGE="en-us",
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "contract-acceptance-email-tests",
        }
    },
)
class SendContractAcceptanceEmailUseCaseTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.use_case = SendContractAcceptanceEmailUseCase()

    def tearDown(self):
        cache.clear()

    @patch("connect.usecases.commerce.send_contract_acceptance_email.send_html_email")
    def test_renders_base_template_with_facts_and_attachment(self, mock_send):
        result = self.use_case.execute(_dto(language="en-us"))

        self.assertTrue(result)
        mock_send.assert_called_once()
        kwargs = mock_send.call_args.kwargs
        self.assertEqual(kwargs["to"], "customer@example.com")
        self.assertEqual(kwargs["subject"], "Your contract")
        self.assertIn(LOGO_URL, kwargs["html_content"])
        self.assertIn("Privacy Policy", kwargs["html_content"])
        self.assertIn("Plan: Growth", kwargs["html_content"])
        self.assertIn("Version: v2.1", kwargs["html_content"])
        self.assertIn("Date: 06/10/2026", kwargs["html_content"])
        self.assertIn("Plan: Growth", kwargs["text_content"])
        self.assertIn("Date: 06/10/2026", kwargs["text_content"])

        attachment = kwargs["attachments"][0]
        self.assertEqual(attachment[0], "contract-v2.1.pdf")
        self.assertEqual(attachment[1], PDF_BYTES)
        self.assertEqual(attachment[2], PDF_MIME_TYPE)

    @patch("connect.usecases.commerce.send_contract_acceptance_email.send_html_email")
    def test_portuguese_and_spanish_use_day_first_date(self, mock_send):
        self.use_case.execute(_dto(language="pt-br"))
        self.use_case.execute(_dto(language="es-MX"))

        portuguese, spanish = (
            call.kwargs["html_content"] for call in mock_send.call_args_list
        )
        self.assertIn("Date: 10/06/2026", portuguese)
        self.assertIn("Date: 10/06/2026", spanish)

    @patch("connect.usecases.commerce.send_contract_acceptance_email.send_html_email")
    def test_unknown_language_falls_back_to_english_date(self, mock_send):
        self.use_case.execute(_dto(language=""))
        self.use_case.execute(_dto(language="fr-FR"))

        for call in mock_send.call_args_list:
            self.assertIn("Date: 06/10/2026", call.kwargs["html_content"])
            self.assertEqual(call.kwargs["subject"], "Your contract")

    @patch("connect.usecases.commerce.send_contract_acceptance_email.send_html_email")
    def test_missing_plan_renders_placeholder(self, mock_send):
        self.use_case.execute(_dto(plan_name=""))

        self.assertIn("Plan: -", mock_send.call_args.kwargs["html_content"])

    @patch("connect.usecases.commerce.send_contract_acceptance_email.send_html_email")
    def test_is_idempotent_for_same_acceptance_id(self, mock_send):
        dto = _dto()

        first = self.use_case.execute(dto)
        second = self.use_case.execute(dto)

        self.assertTrue(first)
        self.assertTrue(second)
        mock_send.assert_called_once()

    @patch("connect.usecases.commerce.send_contract_acceptance_email.send_html_email")
    def test_distinct_acceptance_ids_send_separately(self, mock_send):
        self.use_case.execute(_dto())
        self.use_case.execute(_dto())

        self.assertEqual(mock_send.call_count, 2)

    @override_settings(SEND_EMAILS=False)
    @patch("connect.usecases.commerce.send_contract_acceptance_email.send_html_email")
    def test_skips_when_send_emails_disabled(self, mock_send):
        result = self.use_case.execute(_dto())

        self.assertFalse(result)
        mock_send.assert_not_called()
