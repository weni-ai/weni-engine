"""Tests for InsightsRESTClient."""

from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from connect.api.v1.internal.insights.insights_rest_client import InsightsRESTClient


@override_settings(INSIGHTS_REST_ENDPOINT="https://insights-engine.weni.ai")
class InsightsRESTClientTestCase(SimpleTestCase):
    @patch(
        "connect.api.v1.internal.insights.insights_rest_client.InternalAuthentication"
    )
    @patch("connect.api.v1.internal.insights.insights_rest_client.requests.post")
    def test_update_user_language_posts_to_change_language_endpoint(
        self, mock_post, mock_auth_class
    ):
        mock_auth_class.return_value.headers = {"Authorization": "Bearer token"}
        mock_response = Mock()
        mock_response.json.return_value = {"status": "ok"}
        mock_post.return_value = mock_response

        result = InsightsRESTClient().update_user_language("user@example.com", "pt-br")

        mock_post.assert_called_once_with(
            url="https://insights-engine.weni.ai/v1/internal/users/change-language/",
            headers={"Authorization": "Bearer token"},
            json={"email": "user@example.com", "language": "pt-br"},
            timeout=60,
        )
        self.assertEqual(result, {"status": "ok"})

    @patch(
        "connect.api.v1.internal.insights.insights_rest_client.InternalAuthentication"
    )
    @patch("connect.api.v1.internal.insights.insights_rest_client.requests.patch")
    def test_notify_vtex_account_migration_patches_project_endpoint(
        self, mock_patch, mock_auth_class
    ):
        mock_auth_class.return_value.headers = {"Authorization": "Bearer token"}
        mock_response = Mock()
        mock_response.content = b'{"updated": true}'
        mock_response.json.return_value = {"updated": True}
        mock_response.raise_for_status = Mock()
        mock_patch.return_value = mock_response

        result = InsightsRESTClient().notify_vtex_account_migration(
            "00000000-0000-0000-0000-000000000001",
            "example",
        )

        mock_patch.assert_called_once_with(
            url=(
                "https://insights-engine.weni.ai/v1/internal/projects/"
                "00000000-0000-0000-0000-000000000001/vtex-account"
            ),
            headers={"Authorization": "Bearer token"},
            json={"vtex_account": "example"},
            timeout=60,
        )
        self.assertEqual(result, {"updated": True})

    @patch(
        "connect.api.v1.internal.insights.insights_rest_client.InternalAuthentication"
    )
    @patch("connect.api.v1.internal.insights.insights_rest_client.requests.patch")
    def test_notify_vtex_account_migration_accepts_null_and_empty_values(
        self, mock_patch, mock_auth_class
    ):
        mock_auth_class.return_value.headers = {"Authorization": "Bearer token"}
        mock_response = Mock()
        mock_response.content = b""
        mock_response.raise_for_status = Mock()
        mock_patch.return_value = mock_response

        client = InsightsRESTClient()

        self.assertEqual(
            client.notify_vtex_account_migration(
                "00000000-0000-0000-0000-000000000001", None
            ),
            {},
        )
        self.assertEqual(
            client.notify_vtex_account_migration(
                "00000000-0000-0000-0000-000000000001", ""
            ),
            {},
        )

        self.assertEqual(mock_patch.call_count, 2)
        self.assertEqual(
            mock_patch.call_args_list[0].kwargs["json"], {"vtex_account": None}
        )
        self.assertEqual(
            mock_patch.call_args_list[1].kwargs["json"], {"vtex_account": ""}
        )
