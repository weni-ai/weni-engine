"""Tests for the NotifyBusinessVerificationView."""

import json
from unittest.mock import patch

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from connect.api.v2.internals.business_verification.views import (
    NotifyBusinessVerificationView,
)


class NotifyBusinessVerificationViewTestCase(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def _post(self, payload):
        request = self.factory.post(
            "/v2/internals/business-verification/notify/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        view = NotifyBusinessVerificationView.as_view()
        response = view(request)
        response.render()
        return response, json.loads(response.content)

    @patch("connect.api.v1.internal.permissions.ModuleHasPermission.has_permission")
    @patch(
        "connect.api.v2.internals.business_verification.views.NotifyBusinessVerificationUseCase"
    )
    def test_approved_returns_200(self, use_case_class, has_permission):
        has_permission.return_value = True
        use_case_class.return_value.execute.return_value = True

        response, content = self._post(
            {
                "user_email": "customer@example.com",
                "status": "APPROVED",
                "verification_attempts": 1,
            }
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(content, {"sent": True})

        use_case_class.return_value.execute.assert_called_once_with(
            user_email="customer@example.com",
            status="APPROVED",
            rejection_reasons=[],
            verification_attempts=1,
            language=None,
        )

    @patch("connect.api.v1.internal.permissions.ModuleHasPermission.has_permission")
    def test_failed_payload_with_reasons(self, has_permission):
        has_permission.return_value = True

        with patch(
            "connect.api.v2.internals.business_verification.views.NotifyBusinessVerificationUseCase"
        ) as use_case_class:
            use_case_class.return_value.execute.return_value = True

            response, _ = self._post(
                {
                    "user_email": "customer@example.com",
                    "status": "FAILED",
                    "rejection_reasons": ["LEGAL_NAME_NOT_FOUND_IN_DOCUMENTS"],
                    "verification_attempts": 2,
                    "language": "pt-br",
                }
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        use_case_class.return_value.execute.assert_called_once_with(
            user_email="customer@example.com",
            status="FAILED",
            rejection_reasons=["LEGAL_NAME_NOT_FOUND_IN_DOCUMENTS"],
            verification_attempts=2,
            language="pt-br",
        )

    @patch("connect.api.v1.internal.permissions.ModuleHasPermission.has_permission")
    def test_rejects_invalid_status(self, has_permission):
        has_permission.return_value = True

        response, _ = self._post(
            {"user_email": "customer@example.com", "status": "UNKNOWN"}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("connect.api.v1.internal.permissions.ModuleHasPermission.has_permission")
    def test_rejects_missing_email(self, has_permission):
        has_permission.return_value = True

        response, _ = self._post({"status": "APPROVED"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("connect.api.v1.internal.permissions.ModuleHasPermission.has_permission")
    def test_returns_403_when_module_permission_denied(self, has_permission):
        has_permission.return_value = False

        response, _ = self._post(
            {"user_email": "customer@example.com", "status": "APPROVED"}
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
