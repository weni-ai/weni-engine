"""Tests for SendContractAcceptanceEmailUseCase."""

import base64
import uuid
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


def _dto(**overrides) -> SendContractAcceptanceEmailDTO:
    defaults = dict(
        user_email="customer@example.com",
        acceptance_id=uuid.uuid4(),
        subject="Seu contrato Weni",
        body_html="<p>Contrato aceito com sucesso</p>",
        file_name="contract-v2.1.pdf",
        file_base64=PDF_BASE64,
    )
    defaults.update(overrides)
    return SendContractAcceptanceEmailDTO(**defaults)


@override_settings(
    SEND_EMAILS=True,
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
    def test_sends_email_with_subject_body_and_attachment(self, mock_send):
        result = self.use_case.execute(_dto())

        self.assertTrue(result)
        mock_send.assert_called_once()
        kwargs = mock_send.call_args.kwargs
        self.assertEqual(kwargs["to"], "customer@example.com")
        self.assertEqual(kwargs["subject"], "Seu contrato Weni")
        self.assertEqual(kwargs["html_content"], "<p>Contrato aceito com sucesso</p>")

        attachment = kwargs["attachments"][0]
        self.assertEqual(attachment[0], "contract-v2.1.pdf")
        self.assertEqual(attachment[1], PDF_BYTES)
        self.assertEqual(attachment[2], PDF_MIME_TYPE)

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
