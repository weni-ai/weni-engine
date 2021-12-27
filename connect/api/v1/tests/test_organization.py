import json
import uuid as uuid4
from unittest.mock import patch
from unittest import skipIf
from django.test import RequestFactory
from django.test import TestCase
from django.test.client import MULTIPART_CONTENT
from rest_framework import status

from connect.api.v1.organization.views import (
    OrganizationViewSet,
    OrganizationAuthorizationViewSet,
)
from connect.api.v1.tests.utils import create_user_and_token
from connect.common.models import Organization, OrganizationAuthorization, BillingPlan, Project


class CreateOrganizationAPITestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.owner, self.owner_token = create_user_and_token("owner")

    def request(self, data, token=None):
        authorization_header = (
            {"HTTP_AUTHORIZATION": "Token {}".format(token.key)} if token else {}
        )

        request = self.factory.post(
            "/v1/organization/org/", data, **authorization_header
        )

        response = OrganizationViewSet.as_view({"post": "create"})(request)
        response.render()
        content_data = json.loads(response.content)
        return (response, content_data)

    @patch("connect.common.tasks.create_organization.delay")
    def test_okay(self, task_create_organization):
        task_create_organization.return_value.result = {"id": 1}
        response, content_data = self.request(
            {
                "name": "Organization 1",
                "description": "This organization is very good",
                "organization_billing_plan": "enterprise",
            },
            self.owner_token,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        organization = Organization.objects.get(pk=content_data.get("uuid"))

        self.assertEqual(organization.name, "Organization 1")
        self.assertEqual(organization.description, "This organization is very good")

        organization_authorization = OrganizationAuthorization.objects.filter(
            organization=organization, user=self.owner
        )

        self.assertEqual(organization_authorization.count(), 1)
        self.assertEqual(
            organization_authorization.first().role,
            OrganizationAuthorization.ROLE_ADMIN,
        )


class ListOrganizationAPITestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.owner, self.owner_token = create_user_and_token("owner")

        self.organization = Organization.objects.create(
            name="test organization", description="", inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="free",
        )
        self.organization_authorization = self.organization.authorizations.create(
            user=self.owner, role=OrganizationAuthorization.ROLE_ADMIN
        )

    def request(self, param, value, token=None):
        authorization_header = (
            {"HTTP_AUTHORIZATION": "Token {}".format(token.key)} if token else {}
        )

        request = self.factory.get(
            "/v1/organization/org/?{}={}".format(param, value), **authorization_header
        )

        response = OrganizationViewSet.as_view({"get": "list"})(
            request, organization=self.organization.uuid
        )
        response.render()
        content_data = json.loads(response.content)
        return (response, content_data)

    def test_okay(self):
        response, content_data = self.request(
            "organization",
            self.organization.uuid,
            self.owner_token,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)


class GetOrganizationContactsAPITestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.owner, self.owner_token = create_user_and_token("owner")

        self.organization = Organization.objects.create(
            name="test organization", description="", inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="free",
        )
        self.organization_authorization = self.organization.authorizations.create(
            user=self.owner, role=OrganizationAuthorization.ROLE_ADMIN
        )

        self.project1 = Project.objects.create(
            name="project 1", flow_organization=uuid4.uuid4(), organization=self.organization,
            contact_count=25,
        )

        self.project2 = Project.objects.create(
            name="project 2", flow_organization=uuid4.uuid4(), organization=self.organization,
            contact_count=5,
        )

    def request(self, param, value, token=None):
        authorization_header = (
            {"HTTP_AUTHORIZATION": "Token {}".format(token.key)} if token else {}
        )

        request = self.factory.get(
            f"/v1/organization/org/{param}/{value}", **authorization_header
        )

        response = OrganizationViewSet.as_view({"get": "get_active_org_contacts"})(
            request, organization_uuid=self.organization.uuid
        )

        content_data = json.loads(response.content)
        return (response, content_data)

    def test_okay(self):
        response, content_data = self.request(
            "organization",
            self.organization.uuid,
            self.owner_token,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(content_data['active-contacts']['organization_active_contacts'], 30)


@skipIf(True, "Skipping test until we find a way to mock flows and AI")
class OrgBillingPlan(TestCase):
    def setUp(self):

        from connect.grpc.types.flow import FlowType
        self.flows = FlowType()

        self.factory = RequestFactory()
        self.owner, self.owner_token = create_user_and_token("owner")

        self.flows_project = self.flows.create_project(project_name='Unit Test', user_email=self.owner.email, project_timezone='America/Maceio')

        self.organization = Organization.objects.create(
            name="test organization", description="", inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="enterprise",
        )
        self.project = Project.objects.create(
            name="Unit Test Project", flow_organization=self.flows_project.uuid,
            organization_id=self.organization.uuid)

    def request(self, param, value, token=None):
        authorization_header = (
            {"HTTP_AUTHORIZATION": "Token {}".format(token.key)} if token else {}
        )

        request = self.factory.post(
            f"/v1/organization/org/billing/{param}/{value}/", **authorization_header
        )
        if param == 'closing-plan':
            response = OrganizationViewSet.as_view({"patch": "closing_plan"})(
                request, organization_uuid=self.organization.uuid
            )
        elif param == 'reactivate-plan':
            response = OrganizationViewSet.as_view({"patch": "reactivate_plan"})(
                request, organization_uuid=self.organization.uuid
            )

        content_data = json.loads(response.content)
        return (response, content_data)

    def test_closing_plan(self):
        response, content_data = self.request(
            "closing-plan",
            self.organization.uuid,
            self.owner_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(content_data['is_active'], False)

    def test_reactivate_plan(self):
        response, content_data = self.request(
            "reactivate-plan",
            self.organization.uuid,
            self.owner_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(content_data['is_active'], True)

    def tearDown(self):
        self.flows.delete_project(project_uuid=self.flows_project.uuid, user_email=self.owner.email)
        self.project.delete()
        self.organization.delete()


class OrgBillingAdditionalInformation(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.owner, self.owner_token = create_user_and_token("owner")

        self.organization = Organization.objects.create(
            name="test organization", description="", inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="enterprise",
        )

        self.organization_authorization = self.organization.authorizations.create(
            user=self.owner, role=OrganizationAuthorization.ROLE_ADMIN
        )

    def request(self, value, data={}, token=None):
        authorization_header = (
            {"HTTP_AUTHORIZATION": "Token {}".format(token.key)} if token else {}
        )
        request = self.factory.post(
            f"/v1/organization/org/billing/add-additional-information/{value}/", **authorization_header,
            data=data,
        )
        response = OrganizationViewSet.as_view({"post": "add_additional_billing_information"})(
            request, organization_uuid=self.organization.uuid
        )
        content_data = json.loads(response.content)

        return response, content_data

    def test_add_aditional_info(self):
        data = {
            'personal_identification_number': '111.111.111-11',
            'additional_data': 'data'
        }
        response, content_data = self.request(self.organization.uuid, data, self.owner_token)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(content_data['status'], 'SUCCESS')

    def test_add_additional_info_void_fields(self):
        data = {
        }
        response, content_data = self.request(self.organization.uuid, data, self.owner_token)
        self.assertEqual(content_data['status'], 'NO CHANGES')

    def tearDown(self):
        self.organization.delete()


class ListOrganizationAuthorizationTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

        self.owner, self.owner_token = create_user_and_token("owner")
        self.user, self.user_token = create_user_and_token()

        self.organization = Organization.objects.create(
            name="test organization", description="", inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="free",
        )
        self.organization_authorization = self.organization.authorizations.create(
            user=self.owner, role=OrganizationAuthorization.ROLE_ADMIN
        )

        self.user_auth = self.organization.get_user_authorization(self.user)
        self.user_auth.role = OrganizationAuthorization.ROLE_CONTRIBUTOR
        self.user_auth.save()

    def request(self, organization, token):
        authorization_header = {"HTTP_AUTHORIZATION": "Token {}".format(token.key)}
        request = self.factory.get(
            "/v1/organization/authorizations/?organization={}".format(organization),
            **authorization_header,
        )
        response = OrganizationAuthorizationViewSet.as_view({"get": "list"})(request)
        response.render()
        content_data = json.loads(response.content)
        return (response, content_data)

    def test_okay(self):
        response, content_data = self.request(self.organization.uuid, self.owner_token)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(content_data.get("count"), 2)

        self.assertEqual(content_data.get("results")[0].get("user"), self.owner.id)
        self.assertEqual(content_data.get("results")[1].get("user"), self.user.id)

    def test_user_forbidden(self):
        response, content_data = self.request(self.organization.uuid, self.user_token)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_organization_not_found(self):
        response, content_data = self.request(uuid4.uuid4(), self.user_token)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_organization_invalid_uuid(self):
        response, content_data = self.request("444-212-2333232", self.user_token)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class UpdateAuthorizationRoleTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

        self.owner, self.owner_token = create_user_and_token("owner")
        self.user, self.user_token = create_user_and_token()

        self.organization = Organization.objects.create(
            name="test organization", description="", inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="free",
        )
        self.organization_authorization = self.organization.authorizations.create(
            user=self.owner, role=OrganizationAuthorization.ROLE_ADMIN
        )

    def request(self, organization, token, user, data):
        authorization_header = {"HTTP_AUTHORIZATION": "Token {}".format(token.key)}
        request = self.factory.patch(
            "/v1/organization/authorizations/{}/{}/".format(organization.uuid, user.pk),
            self.factory._encode_data(data, MULTIPART_CONTENT),
            MULTIPART_CONTENT,
            **authorization_header,
        )
        view = OrganizationAuthorizationViewSet.as_view({"patch": "update"})
        response = view(request, organization__uuid=organization.uuid, user__id=user.pk)
        response.render()
        content_data = json.loads(response.content)
        return (response, content_data)

    def test_okay(self):
        response, content_data = self.request(
            self.organization,
            self.owner_token,
            self.user,
            {"role": OrganizationAuthorization.ROLE_CONTRIBUTOR},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            content_data.get("role"), OrganizationAuthorization.ROLE_CONTRIBUTOR
        )

        user_authorization = self.organization.get_user_authorization(self.user)
        self.assertEqual(
            user_authorization.role, OrganizationAuthorization.ROLE_CONTRIBUTOR
        )

    def test_forbidden(self):
        response, content_data = self.request(
            self.organization,
            self.user_token,
            self.user,
            {"role": OrganizationAuthorization.ROLE_CONTRIBUTOR},
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_t_set_your_role(self):
        response, content_data = self.request(
            self.organization,
            self.owner_token,
            self.owner,
            {"role": OrganizationAuthorization.ROLE_CONTRIBUTOR},
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class DestroyAuthorizationRoleTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

        self.owner, self.owner_token = create_user_and_token("owner")
        self.user, self.user_token = create_user_and_token()

        self.organization = Organization.objects.create(
            name="test organization", description="", inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="free",
        )
        self.organization_authorization = self.organization.authorizations.create(
            user=self.owner, role=OrganizationAuthorization.ROLE_ADMIN
        )

        self.user_organization_authorization = self.organization.authorizations.create(
            user=self.user, role=OrganizationAuthorization.ROLE_CONTRIBUTOR
        )

    def request(self, organization, token, user):
        authorization_header = {"HTTP_AUTHORIZATION": "Token {}".format(token.key)}
        request = self.factory.delete(
            "/v1/organization/authorizations/{}/{}/".format(organization.uuid, user.pk),
            **authorization_header,
        )
        view = OrganizationAuthorizationViewSet.as_view({"delete": "destroy"})
        response = view(request, organization__uuid=organization.uuid, user__id=user.pk)
        response.render()
        return response

    def test_okay(self):
        response = self.request(self.organization, self.owner_token, self.user)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_forbidden(self):
        response = self.request(
            self.organization,
            self.user_token,
            self.user,
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class ActiveContactsLimitTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.owner, self.owner_token = create_user_and_token("owner")

        self.organization = Organization.objects.create(
            name="test organization", description="", inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="free",
        )
        self.enterprise_org = Organization.objects.create(
            name="test organization enterprise", description="", inteligence_organization=2,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="enterprise",
        )
        self.custom_org = Organization.objects.create(
            name="test organization custom", description="", inteligence_organization=3,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="custom",
        )

        self.project = Project.objects.create(
            name="Unit Test Project", flow_organization=uuid4.uuid4(),
            organization_id=self.organization.uuid)

        self.organization_authorization = self.organization.authorizations.create(
            user=self.owner, role=OrganizationAuthorization.ROLE_ADMIN
        )

        self.organization_authorization_enterprise = self.enterprise_org.authorizations.create(
            user=self.owner, role=OrganizationAuthorization.ROLE_ADMIN
        )

        self.organization_authorization_enterprise = self.custom_org.authorizations.create(
            user=self.owner, role=OrganizationAuthorization.ROLE_ADMIN
        )

    def request(self, param, value, token=None):
        authorization_header = (
            {"HTTP_AUTHORIZATION": "Token {}".format(token.key)} if token else {}
        )

        request = self.factory.get(
            f"/v1/organization/org/billing/{param}/{value}/", **authorization_header
        )
        response = OrganizationViewSet.as_view({"get": "organization_on_limit"})(
            request, organization_uuid=value
        )

        content_data = json.loads(response.content)
        return (response, content_data)

    def request2(self, param, method, token=None):
        authorization_header = (
            {"HTTP_AUTHORIZATION": "Token {}".format(token.key)} if token else {}
        )
        if method == 'GET':
            request = self.factory.get(
                f"/v1/organization/org/billing/{param}/", **authorization_header
            )

            response = OrganizationViewSet.as_view({"get": "active_contacts_limit"})(
                request
            )
        else:
            request = self.factory.patch(
                f"/v1/organization/org/billing/{param}/", **authorization_header,
            )

            response = OrganizationViewSet.as_view({"patch": "active_contacts_limit"})(
                request
            )

        content_data = json.loads(response.content)
        return (response, content_data)

    def test_organization_on_limit(self):
        response, content_data = self.request(
            "organization-on-limit",
            self.organization.uuid,
            self.owner_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual("free plan is valid yet", content_data["message"])

    def test_organization_over_limit(self):
        self.project2 = Project.objects.create(
            name="Unit Test Project 2", flow_organization=uuid4.uuid4(),
            organization_id=self.organization.uuid, contact_count=250
        )
        response, content_data = self.request(
            "organization-on-limit",
            self.organization.uuid,
            self.owner_token,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual("free plan isn't longer valid", content_data['message'])

    def test_organization_limit_custom(self):
        response, content_data = self.request(
            "organization-on-limit",
            self.custom_org.uuid,
            self.owner_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual("Your plan don't have a contact active limit", content_data['message'])

    def test_organization_limit_enterprise(self):
        response, content_data = self.request(
            "organization-on-limit",
            self.enterprise_org.uuid,
            self.owner_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual("Your plan don't have a contact active limit", content_data['message'])

    def test_get_active_contacts_limit(self):
        response, content_data = self.request2(
            "active-contacts-limit",
            'GET',
            self.owner_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(content_data['active_contacts_limit'], 200)

    def tearDown(self):
        self.project.delete()
        self.organization.delete()


class ExtraIntegrationsTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

        self.owner, self.owner_token = create_user_and_token("owner")
        self.user, self.user_token = create_user_and_token()
        self.organization = Organization.objects.create(
            name="test organization", description="", inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="free", extra_integration=4,
        )

        self.project = Project.objects.create(
            name="Unit Test Project", flow_organization="57257d94-e54b-4ec1-8952-113a81610465",
            organization_id=self.organization.uuid)

        self.organization_authorization = self.organization.authorizations.create(
            user=self.owner, role=OrganizationAuthorization.ROLE_ADMIN
        )

    def request(self, value, param, token=None):
        authorization_header = (
            {"HTTP_AUTHORIZATION": "Token {}".format(token.key)} if token else {}
        )
        request = self.factory.get(
            f"/v1/organization/org/billing/{value}/{param}", **authorization_header
        )
        response = OrganizationViewSet.as_view({"get": "get_extra_active_integrations"})(
            request, organization_uuid=self.organization.uuid
        )

        content_data = json.loads(response.content)

        return response, content_data

    def test_extra_integration(self):
        response, content_data = self.request(
            "extra-integrations",
            self.organization.uuid,
            self.owner_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
