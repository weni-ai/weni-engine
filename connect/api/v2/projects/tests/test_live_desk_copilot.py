import json
from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from connect.api.v1.tests.utils import create_user_and_token
from connect.api.v2.projects.serializers import ProjectSerializer
from connect.api.v2.projects.views import ProjectViewSet
from connect.common.mocks import StripeMockGateway
from connect.common.models import (
    BillingPlan,
    Organization,
    OrganizationRole,
    Project,
)


@override_settings(USE_EDA_PERMISSIONS=False, EDA_PRODUCER="connect-test-producer")
class LiveDeskCopilotProjectSerializerTestCase(TestCase):
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway):
        mock_get_gateway.return_value = StripeMockGateway()
        self.user, _ = create_user_and_token("copilot_user")
        self.organization = Organization.objects.create(
            name="Copilot Org",
            description="Copilot Org",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        self.organization.authorizations.create(
            user=self.user, role=OrganizationRole.ADMIN.value
        )
        self.parent_project = Project.objects.create(
            name="Parent Project",
            organization=self.organization,
            created_by=self.user,
            vtex_account="parent-store",
        )
        self.other_organization = Organization.objects.create(
            name="Other Org",
            description="Other Org",
            inteligence_organization=2,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        self.foreign_parent = Project.objects.create(
            name="Foreign Parent",
            organization=self.other_organization,
            created_by=self.user,
        )

    def _build_serializer(self, data):
        request = MagicMock()
        request.user = self.user
        request.data = data
        return ProjectSerializer(data=data, context={"request": request})

    def _valid_copilot_payload(self, **overrides):
        payload = {
            "name": "Live Desk Copilot",
            "timezone": "America/Sao_Paulo",
            "organization": str(self.organization.uuid),
            "is_live_desk_copilot": True,
            "parent_project_uuid": str(self.parent_project.uuid),
        }
        payload.update(overrides)
        return payload

    def test_create_persists_copilot_flag_and_parent(self):
        serializer = self._build_serializer(self._valid_copilot_payload())

        with patch(
            "connect.api.v2.projects.serializers.RabbitmqPublisher"
        ) as mock_rabbitmq, patch(
            "connect.api.v2.projects.serializers.EDAPublisher"
        ) as mock_eda:
            mock_rabbitmq.return_value = Mock()
            mock_eda.return_value = Mock()
            self.assertTrue(serializer.is_valid(), serializer.errors)
            instance = serializer.save()

        instance.refresh_from_db()
        self.assertTrue(instance.is_live_desk_copilot)
        self.assertEqual(instance.parent_project_id, self.parent_project.uuid)
        self.assertIsNone(instance.vtex_account)

    def test_create_publishes_copilot_fields_on_eda(self):
        serializer = self._build_serializer(self._valid_copilot_payload())

        with patch(
            "connect.api.v2.projects.serializers.RabbitmqPublisher"
        ) as mock_rabbitmq, patch(
            "connect.api.v2.projects.serializers.EDAPublisher"
        ) as mock_eda:
            mock_rabbitmq_instance = Mock()
            mock_rabbitmq.return_value = mock_rabbitmq_instance
            mock_eda.return_value = Mock()
            self.assertTrue(serializer.is_valid(), serializer.errors)
            serializer.save()

        rabbitmq_body = mock_rabbitmq_instance.send_message.call_args.args[0]
        self.assertTrue(rabbitmq_body["is_live_desk_copilot"])
        self.assertTrue(rabbitmq_body["brain_on"])
        self.assertEqual(
            rabbitmq_body["parent_project_uuid"], str(self.parent_project.uuid)
        )
        self.assertIsNone(rabbitmq_body["vtex_account"])

        amazonmq_body = mock_eda.return_value.send_message.call_args.args[0]
        self.assertEqual(amazonmq_body["event_type"], "project.created")
        self.assertEqual(amazonmq_body["data"], rabbitmq_body)

    def test_regular_create_defaults_copilot_fields_to_false_and_null(self):
        serializer = self._build_serializer(
            {
                "name": "Regular Project",
                "timezone": "America/Sao_Paulo",
                "organization": str(self.organization.uuid),
            }
        )

        with patch(
            "connect.api.v2.projects.serializers.RabbitmqPublisher"
        ) as mock_rabbitmq, patch(
            "connect.api.v2.projects.serializers.EDAPublisher"
        ) as mock_eda:
            mock_rabbitmq_instance = Mock()
            mock_rabbitmq.return_value = mock_rabbitmq_instance
            mock_eda.return_value = Mock()
            self.assertTrue(serializer.is_valid(), serializer.errors)
            instance = serializer.save()

        instance.refresh_from_db()
        self.assertFalse(instance.is_live_desk_copilot)
        self.assertIsNone(instance.parent_project_id)
        rabbitmq_body = mock_rabbitmq_instance.send_message.call_args.args[0]
        self.assertFalse(rabbitmq_body["is_live_desk_copilot"])
        self.assertFalse(rabbitmq_body["brain_on"])
        self.assertIsNone(rabbitmq_body["parent_project_uuid"])

    def test_copilot_without_parent_is_invalid(self):
        serializer = self._build_serializer(
            self._valid_copilot_payload(parent_project_uuid=None)
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("parent_project_uuid", serializer.errors)
        self.assertIn(
            "required when is_live_desk_copilot is true",
            str(serializer.errors["parent_project_uuid"]),
        )

    def test_copilot_omitting_parent_key_is_invalid(self):
        payload = self._valid_copilot_payload()
        del payload["parent_project_uuid"]
        serializer = self._build_serializer(payload)

        self.assertFalse(serializer.is_valid())
        self.assertIn("parent_project_uuid", serializer.errors)

    def test_parent_without_copilot_flag_is_invalid(self):
        serializer = self._build_serializer(
            {
                "name": "Regular Project",
                "timezone": "America/Sao_Paulo",
                "organization": str(self.organization.uuid),
                "is_live_desk_copilot": False,
                "parent_project_uuid": str(self.parent_project.uuid),
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("parent_project_uuid", serializer.errors)
        self.assertIn(
            "only allowed when is_live_desk_copilot is true",
            str(serializer.errors["parent_project_uuid"]),
        )

    def test_missing_parent_is_invalid(self):
        serializer = self._build_serializer(
            self._valid_copilot_payload(parent_project_uuid=str(uuid4()))
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("parent_project_uuid", serializer.errors)
        self.assertIn("not found", str(serializer.errors["parent_project_uuid"]))

    def test_parent_from_another_organization_is_invalid(self):
        serializer = self._build_serializer(
            self._valid_copilot_payload(
                parent_project_uuid=str(self.foreign_parent.uuid)
            )
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("parent_project_uuid", serializer.errors)
        self.assertIn(
            "same organization",
            str(serializer.errors["parent_project_uuid"]),
        )

    def test_nested_copilot_parent_is_invalid(self):
        copilot_parent = Project.objects.create(
            name="Already Copilot",
            organization=self.organization,
            created_by=self.user,
            is_live_desk_copilot=True,
            parent_project=self.parent_project,
        )
        serializer = self._build_serializer(
            self._valid_copilot_payload(parent_project_uuid=str(copilot_parent.uuid))
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("parent_project_uuid", serializer.errors)
        self.assertIn(
            "cannot be a live desk copilot",
            str(serializer.errors["parent_project_uuid"]),
        )

    def test_response_includes_copilot_fields(self):
        serializer = self._build_serializer(self._valid_copilot_payload())

        with patch("connect.api.v2.projects.serializers.RabbitmqPublisher"), patch(
            "connect.api.v2.projects.serializers.EDAPublisher"
        ):
            self.assertTrue(serializer.is_valid(), serializer.errors)
            instance = serializer.save()

        data = ProjectSerializer(
            instance, context={"request": serializer.context["request"]}
        ).data
        self.assertTrue(data["is_live_desk_copilot"])
        self.assertEqual(data["parent_project_uuid"], str(self.parent_project.uuid))


@override_settings(
    USE_EDA_PERMISSIONS=False,
    EDA_PRODUCER="connect-test-producer",
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "live-desk-copilot-api-tests",
        }
    },
)
class LiveDeskCopilotProjectApiTestCase(TestCase):
    """HTTP create flow through ProjectViewSet (auth + validation + persist)."""

    @patch("connect.common.signals.update_user_permission_project")
    @patch("connect.billing.get_gateway")
    @patch(
        "connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.update_user_permission_project"
    )
    @patch(
        "connect.api.v1.internal.integrations.integrations_rest_client.IntegrationsRESTClient.update_user_permission_project"
    )
    def setUp(self, integrations_rest, flows_rest, mock_get_gateway, mock_permission):
        integrations_rest.side_effect = [200, 200]
        flows_rest.side_effect = [200, 200]
        mock_get_gateway.return_value = StripeMockGateway()
        mock_permission.return_value = True
        cache.clear()

        self.factory = APIRequestFactory()
        self.user, _ = create_user_and_token("copilot_api_user")
        self.organization = Organization.objects.create(
            name="Copilot API Org",
            description="Copilot API Org",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        self.organization.authorizations.create(
            user=self.user, role=OrganizationRole.ADMIN.value
        )
        self.parent_project = Project.objects.create(
            name="Parent Project",
            organization=self.organization,
            created_by=self.user,
            vtex_account="parent-store",
        )

    def tearDown(self):
        cache.clear()

    def _post_create(self, data):
        request = self.factory.post(
            f"/v2/organizations/{self.organization.uuid}/projects/",
            data,
            format="json",
        )
        force_authenticate(request, user=self.user, token=self.user.auth_token)
        with patch("connect.api.v2.projects.serializers.RabbitmqPublisher"), patch(
            "connect.api.v2.projects.serializers.EDAPublisher"
        ):
            response = ProjectViewSet.as_view({"post": "create"})(
                request, organization_uuid=str(self.organization.uuid)
            )
            response.render()
        body = json.loads(response.content) if response.content else {}
        return response, body

    def test_post_creates_copilot_linked_to_parent(self):
        response, body = self._post_create(
            {
                "name": "Live Desk Copilot",
                "timezone": "America/Sao_Paulo",
                "is_live_desk_copilot": True,
                "parent_project_uuid": str(self.parent_project.uuid),
            }
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(body["is_live_desk_copilot"])
        self.assertEqual(body["parent_project_uuid"], str(self.parent_project.uuid))
        self.assertIsNone(body.get("vtex_account"))

        copilot = Project.objects.get(uuid=body["uuid"])
        self.assertTrue(copilot.is_live_desk_copilot)
        self.assertEqual(copilot.parent_project_id, self.parent_project.uuid)
        self.assertIsNone(copilot.vtex_account)

    def test_post_rejects_copilot_without_parent(self):
        response, body = self._post_create(
            {
                "name": "Live Desk Copilot",
                "timezone": "America/Sao_Paulo",
                "is_live_desk_copilot": True,
            }
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("parent_project_uuid", body)

    def test_post_rejects_nested_copilot_parent(self):
        nested = Project.objects.create(
            name="Already Copilot",
            organization=self.organization,
            created_by=self.user,
            is_live_desk_copilot=True,
            parent_project=self.parent_project,
        )
        response, body = self._post_create(
            {
                "name": "Nested Copilot",
                "timezone": "America/Sao_Paulo",
                "is_live_desk_copilot": True,
                "parent_project_uuid": str(nested.uuid),
            }
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("parent_project_uuid", body)
        self.assertEqual(Project.objects.filter(name="Nested Copilot").count(), 0)
