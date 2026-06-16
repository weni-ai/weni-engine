import json
import unittest
import uuid

from rest_framework import status
from rest_framework.test import (
    APIRequestFactory,
    APITestCase,
    APIClient,
    force_authenticate,
)

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.crypto import get_random_string

from unittest.mock import Mock, patch

from connect.api.v1.tests.utils import create_user_and_token
from connect.authentication.models import User, UserEmailSetup
from connect.common.models import (
    BillingPlan,
    Organization,
    OrganizationAuthorization,
    OrganizationRole,
    Project,
    TypeProject,
)
from connect.api.v2.organizations.views import OrganizationViewSet
from connect.common.mocks import StripeMockGateway
from connect.usecases.organizations.list_by_user import ListOrgsByUserUseCase

from connect.api.v1.tests.utils import create_contacts
from connect.billing.tasks import daily_contact_count
import pendulum


class OrganizationViewSetTestCase(TestCase):
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway):
        mock_get_gateway.return_value = StripeMockGateway()

        self.integrations_rest = patch(
            "connect.api.v1.internal.integrations.integrations_rest_client.IntegrationsRESTClient.update_user_permission_project"
        )
        self.flows_rest = patch(
            "connect.api.v1.internal.flows.flows_rest_client.FlowsRESTClient.update_user_permission_project"
        )
        self.integrations_rest_mock = self.integrations_rest.start()
        self.flows_rest_mock = self.flows_rest.start()
        self.integrations_rest_mock.return_value = [200, 200]
        self.flows_rest_mock.return_value = [200, 200]

        self.factory = APIRequestFactory()
        self.user, self.user_token = create_user_and_token("user")
        self.user_1, self.user_1_token = create_user_and_token("user_1")
        self.user_403, self.user_403_token = create_user_and_token("user_403")

        self.org_1 = Organization.objects.create(
            name="V2 Org 1",
            description="V2 Org 1",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )

        self.org_2 = Organization.objects.create(
            name="V2 Org 2",
            description="V2 Org 2",
            inteligence_organization=2,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_ADVANCED,
        )

        self.org_3 = Organization.objects.create(
            name="V2 Org 3",
            description="V2 Org 3",
            inteligence_organization=3,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_SCALE,
        )

        self.org_auth_1 = self.org_1.authorizations.create(
            user=self.user, role=OrganizationRole.ADMIN.value
        )

        self.org_auth_2 = self.org_2.authorizations.create(
            user=self.user, role=OrganizationRole.CONTRIBUTOR.value
        )

    def make_request(self, path, method, data):
        for key in method:
            if key == "post":
                request = self.factory.post(path, data, format="json")
            elif key == "delete":
                request = self.factory.delete(path)
            else:
                request = self.factory.get(path)
            return request

    def request(
        self, path: str, method: dict, pk: str = None, data: dict = None, user=None
    ):
        content_data = ""

        if pk:
            path += f"{pk}"

        request = self.make_request(path, method, data)

        force_authenticate(request, user=user, token=user.auth_token)

        response = OrganizationViewSet.as_view(method)(request, uuid=pk, data=data)
        response.render()

        if not response.status_code == status.HTTP_204_NO_CONTENT:
            content_data = json.loads(response.content)
        return response, content_data

    @unittest.skip("Test broken, need to configure rabbitmq")
    def test_get_organization(self):
        pk = str(self.org_1.uuid)
        path = "/v2/organizations/"
        method = {"get": "retrieve"}
        user = self.user
        auth = self.org_1.get_user_authorization(self.user)
        response, content_data = self.request(path, method, pk=pk, user=user)

        self.assertEquals(response.status_code, status.HTTP_200_OK)
        self.assertEquals(content_data.get("authorization").get("uuid"), str(auth.uuid))
        self.assertEquals(content_data.get("uuid"), pk)

    @unittest.skip("Test broken, need to configure rabbitmq")
    def test_fail_get_authorization(self):
        pk = str(self.org_1.uuid)
        path = "/v2/organizations/"
        method = {"get": "retrieve"}
        user = self.user_403

        response, content_data = self.request(path, method, pk=pk, user=user)
        self.assertEquals(response.status_code, status.HTTP_404_NOT_FOUND)

    @unittest.skip("Test broken, need to configure rabbitmq")
    def test_list_organizations(self):
        path = "/v2/organizations/"
        method = {"get": "list"}
        user = self.user
        response, content_data = self.request(path, method, user=user)
        self.assertEquals(response.status_code, status.HTTP_200_OK)

    @unittest.skip("Test broken, need to configure rabbitmq")
    @patch("connect.billing.get_gateway")
    @patch("connect.authentication.models.User.send_request_flow_user_info")
    @patch(
        "connect.internals.event_driven.producer.rabbitmq_publisher.RabbitmqPublisher"
    )
    def test_create_organization_project(
        self, mock_publisher, send_request_flow_user_info, mock_get_gateway
    ):
        mock_get_gateway.return_value = StripeMockGateway()
        send_request_flow_user_info.side_effect = [True]
        mock_publisher.side_effect = [True]
        org_data = {
            "name": "V2",
            "description": "V2 desc",
            "organization_billing_plan": BillingPlan.PLAN_TRIAL,
            "authorizations": [
                {"user_email": "e@mail.com", "role": 3},
                {"user_email": "user_1@user.com", "role": 3},
            ],
        }

        project_data = {
            "date_format": "D",
            "name": "Test Project",
            "timezone": "America/Argentina/Buenos_Aires",
        }

        data = {"organization": org_data, "project": project_data}

        path = "/v2/organizations/"
        method = {"post": "create"}
        user = self.user

        response, content_data = self.request(path, method, user=user, data=data)

        self.assertEquals(response.status_code, status.HTTP_201_CREATED)

    @unittest.skip("Test broken, need to configure rabbitmq")
    @patch("connect.billing.get_gateway")
    @patch("connect.authentication.models.User.send_request_flow_user_info")
    @patch(
        "connect.internals.event_driven.producer.rabbitmq_publisher.RabbitmqPublisher"
    )
    def test_cannot_create_organization_with_invalid_name_length(
        self, mock_publisher, send_request_flow_user_info, mock_get_gateway
    ):
        mock_get_gateway.return_value = StripeMockGateway()
        send_request_flow_user_info.side_effect = [True]
        mock_publisher.side_effect = [True]

        invalid_name_length = Organization.name.field.max_length + 1

        org_data = {
            "name": get_random_string(invalid_name_length),
            "description": "V2 desc",
            "organization_billing_plan": BillingPlan.PLAN_TRIAL,
            "authorizations": [
                {"user_email": "e@mail.com", "role": 3},
                {"user_email": "user_1@user.com", "role": 3},
            ],
        }

        project_data = {
            "date_format": "D",
            "name": "Test Project",
            "timezone": "America/Argentina/Buenos_Aires",
        }

        data = {"organization": org_data, "project": project_data}

        path = "/v2/organizations/"
        method = {"post": "create"}
        user = self.user

        response, content_data = self.request(path, method, user=user, data=data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["organization"]["name"][0].code, "max_length")

    @unittest.skip("Test broken, need to be fixed")
    @patch("connect.billing.get_gateway")
    @patch("connect.authentication.models.User.send_request_flow_user_info")
    @patch(
        "connect.internals.event_driven.producer.rabbitmq_publisher.RabbitmqPublisher"
    )
    def test_cannot_create_organization_project_with_invalid_name_length(
        self, mock_publisher, send_request_flow_user_info, mock_get_gateway
    ):
        mock_get_gateway.return_value = StripeMockGateway()
        send_request_flow_user_info.side_effect = [True]
        mock_publisher.side_effect = [True]

        org_data = {
            "name": "Test",
            "description": "V2 desc",
            "organization_billing_plan": BillingPlan.PLAN_TRIAL,
            "authorizations": [
                {"user_email": "e@mail.com", "role": 3},
                {"user_email": "user_1@user.com", "role": 3},
            ],
        }

        invalid_name_length = Project.name.field.max_length + 1

        project_data = {
            "date_format": "D",
            "name": get_random_string(invalid_name_length),
            "timezone": "America/Argentina/Buenos_Aires",
        }

        data = {"organization": org_data, "project": project_data}

        path = "/v2/organizations/"
        method = {"post": "create"}
        user = self.user

        response, content_data = self.request(path, method, user=user, data=data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["project"]["name"][0].code, "max_length")

    @unittest.skip("Test broken, need to be fixed")
    @patch(
        "connect.internals.event_driven.producer.rabbitmq_publisher.RabbitmqPublisher.send_message"
    )
    @patch(
        "connect.internals.event_driven.producer.rabbitmq_publisher.RabbitmqPublisher.send_message"
    )
    @patch("connect.authentication.models.User.send_request_flow_user_info")
    def test_user_email_setup(self, mock_publisher, send_request_flow_user_info):
        UserEmailSetup.objects.create(
            user=self.user,
            receive_project_emails=False,
            receive_organization_emails=False,
        )
        send_request_flow_user_info.side_effect = [True]
        mock_publisher.side_effect = [True]
        org_data = {
            "name": "Email Setup",
            "description": "Email Setup",
            "organization_billing_plan": BillingPlan.PLAN_TRIAL,
            "authorizations": [
                {"user_email": "e@mail.com", "role": 3},
                {"user_email": "user_1@user.com", "role": 3},
            ],
        }

        project_data = {
            "date_format": "D",
            "name": "Email Setup",
            "timezone": "America/Argentina/Buenos_Aires",
        }

        data = {"organization": org_data, "project": project_data}

        path = "/v2/organizations/"
        method = {"post": "create"}
        user = self.user

        response, content_data = self.request(path, method, user=user, data=data)

        self.assertEquals(response.status_code, status.HTTP_201_CREATED)


@unittest.skip("Test broken, need to configure rabbitmq")
class OrganizationTestCase(TestCase):
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway):
        mock_get_gateway.return_value = StripeMockGateway()
        self.factory = APIRequestFactory()
        self.user, self.user_token = create_user_and_token("user")

        self.org = Organization.objects.create(
            name="V2 Org 1",
            description="V2 Org 1",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )

        self.auth = self.org.authorizations.create(
            user=self.user, role=OrganizationRole.ADMIN.value
        )

    @patch(
        "connect.api.v1.internal.intelligence.intelligence_rest_client.IntelligenceRESTClient.create_organization"
    )
    def test_create_ai_organization(self, create_organization):
        intelligence_organization = 555
        create_organization.side_effect = [{"id": intelligence_organization}]
        organization = self.org
        created, data = organization.create_ai_organization(self.auth.user.email)
        self.assertTrue(created)
        self.assertEquals(intelligence_organization, data)

    @patch(
        "connect.api.v1.internal.intelligence.intelligence_rest_client.IntelligenceRESTClient.create_organization"
    )
    def test_error_create_ai_organization(self, create_organization):
        organization = self.org
        create_organization.side_effect = [Exception("Error")]
        created, data = organization.create_ai_organization(self.auth.user.email)
        self.assertFalse(created)
        self.assertEquals(data.get("status"), status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEquals(
            data.get("data").get("message"),
            "Could not create organization in AI module",
        )


@unittest.skip("Test broken, need to configure rabbitmq")
class OrganizationAuthorizationTestCase(TestCase):
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway):
        mock_get_gateway.return_value = StripeMockGateway()

        self.owner, self.owner_token = create_user_and_token("owner")
        self.org1 = Organization.objects.create(
            name="Test project methods",
            description="",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__payment_method=BillingPlan.PAYMENT_METHOD_CREDIT_CARD,
            organization_billing__plan=BillingPlan.PLAN_ENTERPRISE,
        )
        self.organization_authorization = self.org1.authorizations.create(
            user=self.owner, role=OrganizationRole.ADMIN.value
        )

    def test_list_project_authorizations(self):
        organization = self.org1
        url = f"/v2/organizations/{organization.uuid}/list-organization-authorizations"
        response = self.client.get(url, HTTP_AUTHORIZATION=f"Token {self.owner_token}")
        self.assertEquals(response.status_code, status.HTTP_200_OK)


@unittest.skip("Test broken, need to configure rabbitmq")
class CustomCountTestCase(TestCase):
    @patch("connect.billing.get_gateway")
    def setUp(self, mock_get_gateway) -> None:
        mock_get_gateway.return_value = StripeMockGateway()

        self.owner, self.owner_token = create_user_and_token("owner")
        self.crm, self.crm_token = create_user_and_token("crm")

        self.org1 = Organization.objects.create(
            name="Test project methods",
            description="",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__payment_method=BillingPlan.PAYMENT_METHOD_CREDIT_CARD,
            organization_billing__plan=BillingPlan.PLAN_ENTERPRISE,
        )
        self.project = self.org1.project.create(name="test case")
        self.organization_authorization = self.org1.authorizations.create(
            user=self.owner, role=OrganizationRole.ADMIN.value
        )

    def test_view(self):
        from freezegun import freeze_time

        # too many loops
        start = pendulum.now().start_of("month")
        end = start.end_of("month")
        period = end - start
        ran = period.range("days")

        for day in ran:
            freezer = freeze_time(day)
            freezer.start()
            create_contacts(num_contacts=10, day=day)
            daily_contact_count()
            freezer.stop()

        organization = self.org1
        url = f"/v2/organizations/{organization.uuid}/get_contact_active?before={end.date()}&after={start.date()}"
        response = self.client.get(
            url, HTTP_AUTHORIZATION=f"Token {self.owner_token}", follow=True
        )
        self.assertEquals(response.status_code, status.HTTP_200_OK)

    def test_view_crm(self):
        from freezegun import freeze_time
        from django.conf import settings

        start = pendulum.now().start_of("month")
        end = start.end_of("month")
        period = end - start
        ran = period.range("days")

        for day in ran:
            freezer = freeze_time(day)
            freezer.start()
            create_contacts(num_contacts=10, day=day)
            daily_contact_count()
            freezer.stop()

        settings.CRM_EMAILS_LIST = [self.crm.email]

        organization = self.org1
        url = f"/v2/organizations/{organization.uuid}/get_contact_active?before={end.date()}&after={start.date()}"
        response = self.client.get(
            url, HTTP_AUTHORIZATION=f"Token {self.crm_token}", follow=True
        )
        self.assertEquals(response.status_code, status.HTTP_200_OK)


@override_settings(USE_EDA_PERMISSIONS=False)
class OrgsByUserBaseTestCase(APITestCase):
    @patch("connect.authentication.signals.RabbitmqPublisher")
    @patch("connect.common.signals.RabbitmqPublisher")
    @patch("connect.common.signals.update_user_permission_project")
    @patch("connect.billing.get_gateway")
    def setUp(
        self,
        mock_get_gateway,
        mock_permission,
        mock_rabbitmq_common,
        mock_rabbitmq_auth,
    ):
        mock_get_gateway.return_value = StripeMockGateway()
        mock_permission.return_value = True
        mock_rabbitmq_common.return_value = Mock()
        mock_rabbitmq_auth.return_value = Mock()

        self.member, _ = create_user_and_token("orgmember")
        self.other, _ = create_user_and_token("orgother")

        self.organization = Organization.objects.create(
            name="member-org",
            description="Organization member-org",
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        OrganizationAuthorization.objects.create(
            user=self.member,
            organization=self.organization,
            role=OrganizationRole.ADMIN.value,
        )
        OrganizationAuthorization.objects.create(
            user=self.other,
            organization=self.organization,
            role=OrganizationRole.CONTRIBUTOR.value,
        )
        self.project = Project.objects.create(
            name="member-project",
            organization=self.organization,
            flow_organization=uuid.uuid4(),
            project_type=TypeProject.COMMERCE,
        )


class ListOrgsByUserUseCaseTestCase(OrgsByUserBaseTestCase):
    def test_returns_orgs_with_projects_and_member_count(self):
        result = ListOrgsByUserUseCase().execute(self.member.email)

        self.assertEqual(len(result), 1)
        org = result[0]
        self.assertEqual(org["uuid"], str(self.organization.uuid))
        self.assertEqual(org["name"], "member-org")
        self.assertEqual(org["member_count"], 2)
        self.assertEqual(
            org["projects"],
            [{"uuid": str(self.project.uuid), "name": "member-project"}],
        )

    def test_excludes_not_setted_role_from_member_count(self):
        ghost, _ = create_user_and_token("ghost")
        OrganizationAuthorization.objects.create(
            user=ghost,
            organization=self.organization,
            role=OrganizationRole.NOT_SETTED.value,
        )

        result = ListOrgsByUserUseCase().execute(self.member.email)

        self.assertEqual(result[0]["member_count"], 2)

    def test_returns_empty_for_unknown_user(self):
        result = ListOrgsByUserUseCase().execute("missing@user.com")
        self.assertEqual(result, [])

    @patch("connect.billing.get_gateway")
    def test_returns_empty_when_only_not_setted_role(self, mock_gateway):
        mock_gateway.return_value = StripeMockGateway()
        loner, _ = create_user_and_token("loner")
        org = Organization.objects.create(
            name="loner-org",
            description="Organization loner-org",
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan=BillingPlan.PLAN_TRIAL,
        )
        OrganizationAuthorization.objects.create(
            user=loner,
            organization=org,
            role=OrganizationRole.NOT_SETTED.value,
        )

        result = ListOrgsByUserUseCase().execute(loner.email)
        self.assertEqual(result, [])


class OrgsByUserViewTestCase(OrgsByUserBaseTestCase):
    def setUp(self):
        super().setUp()
        self.client = APIClient()

        content_type = ContentType.objects.get_for_model(User)
        permission, _ = Permission.objects.get_or_create(
            codename="can_communicate_internally",
            name="can communicate internally",
            content_type=content_type,
        )
        self.member.user_permissions.add(permission)
        self.client.force_authenticate(user=self.member)
        self.url = reverse("orgs-by-user")

    def test_returns_200_with_organizations(self):
        response = self.client.get(self.url, {"user_email": self.member.email})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["organizations"]), 1)
        self.assertEqual(
            response.data["organizations"][0]["uuid"],
            str(self.organization.uuid),
        )

    def test_missing_user_email_returns_400(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_request_returns_403(self):
        unauth_client = APIClient()
        no_perm, _ = create_user_and_token("orgnoperm")
        unauth_client.force_authenticate(user=no_perm)

        response = unauth_client.get(self.url, {"user_email": self.member.email})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class OrganizationAuthorizationViewSetTestCase(TestCase):
    def test_get_serializer_class_returns_nested_authorization_serializer(self):
        from connect.api.v2.organizations.serializers import (
            NestedAuthorizationOrganizationSerializer,
        )
        from connect.api.v2.organizations.views import OrganizationAuthorizationViewSet

        view = OrganizationAuthorizationViewSet()
        self.assertIs(
            view.get_serializer_class(), NestedAuthorizationOrganizationSerializer
        )
