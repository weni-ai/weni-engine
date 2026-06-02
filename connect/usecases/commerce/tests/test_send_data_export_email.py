"""Tests for SendDataExportEmailUseCase."""

from datetime import date
from unittest.mock import patch

from django.test import TestCase, override_settings

from connect.authentication.models import User
from connect.usecases.commerce.dto import SendDataExportEmailDTO
from connect.usecases.commerce.send_data_export_email import (
    TEMPLATE_HTML,
    TEMPLATE_TXT,
    SendDataExportEmailUseCase,
)


def _dto(**overrides) -> SendDataExportEmailDTO:
    defaults = dict(
        user_email="customer@example.com",
        file_url="https://files.example.com/export.csv",
        start_date=date(2026, 4, 1),
        end_date=date(2026, 5, 1),
        template="all",
        status="all",
        language=None,
    )
    defaults.update(overrides)
    return SendDataExportEmailDTO(**defaults)


@override_settings(SEND_EMAILS=True, DEFAULT_LANGUAGE="en-us")
class SendDataExportEmailUseCaseTestCase(TestCase):
    def setUp(self):
        self.use_case = SendDataExportEmailUseCase()
        self.user = User.objects.create(
            email="customer@example.com",
            username="customer",
            first_name="Alice",
            language="pt-br",
        )

    @patch("connect.usecases.commerce.send_data_export_email.send_email")
    def test_sends_email_with_expected_context(self, mock_send):
        result = self.use_case.execute(_dto(language="en-us"))

        self.assertTrue(result)
        mock_send.assert_called_once()
        kwargs = mock_send.call_args.kwargs
        self.assertEqual(kwargs["to"], "customer@example.com")
        self.assertEqual(kwargs["template_txt"], TEMPLATE_TXT)
        self.assertEqual(kwargs["template_html"], TEMPLATE_HTML)
        self.assertEqual(
            kwargs["context"]["file_url"], "https://files.example.com/export.csv"
        )

    @patch("connect.usecases.commerce.send_data_export_email.send_email")
    def test_period_uses_month_first_format_for_english(self, mock_send):
        self.use_case.execute(_dto(language="en-us"))

        context = mock_send.call_args.kwargs["context"]
        self.assertEqual(context["period"], "04/01/2026 ~ 05/01/2026")

    @patch("connect.usecases.commerce.send_data_export_email.send_email")
    def test_period_uses_day_first_format_for_portuguese(self, mock_send):
        self.use_case.execute(_dto(language="pt-br"))

        context = mock_send.call_args.kwargs["context"]
        self.assertEqual(context["period"], "01/04/2026 ~ 01/05/2026")

    @patch("connect.usecases.commerce.send_data_export_email.send_email")
    def test_status_enum_is_translated(self, mock_send):
        self.use_case.execute(_dto(language="en-us", status="delivered"))

        context = mock_send.call_args.kwargs["context"]
        self.assertEqual(context["status_label"], "Delivered")

    @patch("connect.usecases.commerce.send_data_export_email.send_email")
    def test_template_all_is_translated(self, mock_send):
        self.use_case.execute(_dto(language="en-us", template="all"))

        context = mock_send.call_args.kwargs["context"]
        self.assertEqual(context["template_label"], "All")

    @patch("connect.usecases.commerce.send_data_export_email.send_email")
    def test_template_other_value_is_passed_through(self, mock_send):
        self.use_case.execute(_dto(language="en-us", template="Black Friday"))

        context = mock_send.call_args.kwargs["context"]
        self.assertEqual(context["template_label"], "Black Friday")

    @patch("connect.usecases.commerce.send_data_export_email.send_email")
    def test_language_resolved_from_user_when_not_provided(self, mock_send):
        self.use_case.execute(_dto(language=None))

        context = mock_send.call_args.kwargs["context"]
        self.assertEqual(context["period"], "01/04/2026 ~ 01/05/2026")

    @patch("connect.usecases.commerce.send_data_export_email.send_email")
    def test_falls_back_to_default_language_for_unknown_user(self, mock_send):
        result = self.use_case.execute(
            _dto(user_email="unknown@example.com", language=None)
        )

        self.assertTrue(result)
        context = mock_send.call_args.kwargs["context"]
        self.assertEqual(context["period"], "04/01/2026 ~ 05/01/2026")

    @override_settings(SEND_EMAILS=False)
    @patch("connect.usecases.commerce.send_data_export_email.send_email")
    def test_skips_when_send_emails_disabled(self, mock_send):
        result = self.use_case.execute(_dto())

        self.assertFalse(result)
        mock_send.assert_not_called()
