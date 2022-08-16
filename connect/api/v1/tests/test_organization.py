import json
from unittest import skipIf
import uuid as uuid4
from unittest.mock import patch
from django.conf import settings
from django.http import JsonResponse
from django.test import RequestFactory
from django.test import TestCase
from django.test.client import MULTIPART_CONTENT
from rest_framework import status

from connect.api.v1.organization.views import (
    OrganizationViewSet,
    OrganizationAuthorizationViewSet,
)
from connect.api.v1.tests.utils import create_user_and_token
from connect.common.models import (
    Organization,
    OrganizationAuthorization,
    BillingPlan,
    Project,
    OrganizationRole,
)


@skipIf(True, "deprecated")
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
            organization_authorization.first().role, OrganizationRole.ADMIN.value
        )


class ListOrganizationAPITestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.owner, self.owner_token = create_user_and_token("owner")

        self.organization = Organization.objects.create(
            name="test organization",
            description="",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="free",
        )
        self.organization_authorization = self.organization.authorizations.create(
            user=self.owner, role=OrganizationRole.ADMIN.value
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
            name="test organization",
            description="",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="free",
        )
        self.organization_authorization = self.organization.authorizations.create(
            user=self.owner, role=OrganizationRole.ADMIN.value
        )

        self.project1 = Project.objects.create(
            name="project 1",
            flow_organization=uuid4.uuid4(),
            organization=self.organization,
            contact_count=25,
        )

        self.project2 = Project.objects.create(
            name="project 2",
            flow_organization=uuid4.uuid4(),
            organization=self.organization,
            contact_count=5,
        )

    def request(self, param, value, method, token=None):
        authorization_header = (
            {"HTTP_AUTHORIZATION": "Token {}".format(token.key)} if token else {}
        )

        request = self.factory.get(
            f"/v1/organization/org/{param}/{value}", **authorization_header
        )

        response = OrganizationViewSet.as_view({"get": f"{method}"})(
            request, organization_uuid=self.organization.uuid
        )

        content_data = json.loads(response.content)
        return (response, content_data)

    def test_okay(self):
        response, content_data = self.request(
            "organization",
            self.organization.uuid,
            "get_active_org_contacts",
            self.owner_token,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            content_data["active-contacts"]["organization_active_contacts"], 30
        )

    def test_contact_active_per_project(self):
        response, content_data = self.request(
            "contact-active-per-project",
            self.organization.uuid,
            "get_contacts_active_per_project",
            self.owner_token,
        )

        contact_count = 0
        for project in content_data["projects"]:
            contact_count += int(project["active_contacts"])

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(contact_count, 30)


class OrgBillingPlan(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.owner, self.owner_token = create_user_and_token("owner")
        self.contributor, self.contributor_token = create_user_and_token("contributor")
        self.financial, self.financial_token = create_user_and_token("financial")

        self.flows_project = {
            "project_name": "Unit Test",
            "user_email": self.owner.email,
            "project_timezone": "America/Maceio",
            "uuid": uuid4.uuid4(),
        }

        self.organization = Organization.objects.create(
            name="test organization",
            description="",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="free",
        )
        self.project = Project.objects.create(
            name="Unit Test Project",
            flow_organization=self.flows_project["uuid"],
            organization_id=self.organization.uuid,
        )
        # Authorizations
        self.admin_organization_authorization = self.organization.authorizations.create(
            user=self.owner, role=OrganizationRole.ADMIN.value
        )
        self.contributor_organization_authorization = (
            self.organization.authorizations.create(
                user=self.contributor, role=OrganizationRole.CONTRIBUTOR.value
            )
        )

        self.financial_organization_authorization = (
            self.organization.authorizations.create(
                user=self.financial, role=OrganizationRole.FINANCIAL.value
            )
        )

    def request(self, param, value, method, token=None):
        authorization_header = (
            {"HTTP_AUTHORIZATION": "Token {}".format(token.key)} if token else {}
        )

        request = self.factory.patch(
            f"/v1/organization/org/billing/{param}/{value}/",
            **authorization_header,
        )

        response = OrganizationViewSet.as_view({"patch": f"{method}"})(
            request,
            organization_uuid=self.organization.uuid,
        )
        if type(response) == JsonResponse:
            content_data = json.loads(response.content)
            return response, content_data

        response.render()
        content_data = json.loads(response.content)
        return response, content_data

    @patch("connect.common.tasks.update_suspend_project.delay")
    def test_closing_plan_admin(self, task):
        task.return_value.result = True
        response, content_data = self.request(
            "closing-plan",
            self.organization.uuid,
            "closing_plan",
            self.owner_token,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(content_data["is_active"], False)

    @patch("connect.common.tasks.update_suspend_project.delay")
    def test_closing_plan_contributor(self, task):
        task.return_value.result = True
        response, content_data = self.request(
            "closing-plan",
            self.organization.uuid,
            "closing_plan",
            self.contributor_token,
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            content_data["detail"], "You do not have permission to perform this action."
        )

    @patch("connect.common.tasks.update_suspend_project.delay")
    def test_closing_plan_financial(self, task):
        task.return_value.result = True
        response, content_data = self.request(
            "closing-plan",
            self.organization.uuid,
            "closing_plan",
            self.financial_token,
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            content_data["detail"], "You do not have permission to perform this action."
        )

    @patch("connect.common.tasks.update_suspend_project.delay")
    def test_reactivate_plan_admin(self, task):
        task.return_value.result = True
        response, content_data = self.request(
            "reactivate-plan",
            self.organization.uuid,
            "reactivate_plan",
            self.owner_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(content_data["is_active"], True)

    @patch("connect.common.tasks.update_suspend_project.delay")
    def test_reactivate_plan_contributor(self, task):
        task.return_value.result = True
        response, content_data = self.request(
            "reactivate-plan",
            self.organization.uuid,
            "reactivate_plan",
            self.contributor_token,
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            content_data["detail"], "You do not have permission to perform this action."
        )

    @patch("connect.common.tasks.update_suspend_project.delay")
    def test_reactivate_plan_financial(self, task):
        task.return_value.result = True
        response, content_data = self.request(
            "reactivate-plan",
            self.organization.uuid,
            "reactivate_plan",
            self.financial_token,
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            content_data["detail"], "You do not have permission to perform this action."
        )

    # Change plan
    def request_change_plan(self, value, data={}, token=None):
        authorization_header = (
            {"HTTP_AUTHORIZATION": "Token {}".format(token.key)} if token else {}
        )
        request = self.factory.patch(
            f"/v1/organization/org/billing/change-plan/{value}/",
            data=json.dumps(data),
            content_type="application/json",
            format="json",
            **authorization_header,
        )
        response = OrganizationViewSet.as_view({"patch": "change_plan"})(
            request,
            organization_uuid=self.organization.uuid,
        )

        if type(response) == JsonResponse:
            content_data = json.loads(response.content)
            return response, content_data

        response.render()
        content_data = json.loads(response.content)
        return response, content_data

    def test_change_plan_admin(self):
        data = {"organization_billing_plan": "enterprise"}
        response, content_data = self.request_change_plan(
            self.organization.uuid, data, self.owner_token
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(content_data["plan"], "enterprise")

    def test_change_plan_contributor(self):
        data = {"organization_billing_plan": "enterprise"}
        response, content_data = self.request_change_plan(
            self.organization.uuid, data, self.contributor_token
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            content_data["detail"], "You do not have permission to perform this action."
        )

    def test_change_plan_financial(self):
        data = {"organization_billing_plan": "enterprise"}
        response, content_data = self.request_change_plan(
            self.organization.uuid, data, self.financial_token
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            content_data["detail"], "You do not have permission to perform this action."
        )

    def test_change_plan_invalid(self):
        data = {"organization_billing_plan": "entprise"}
        response, content_data = self.request_change_plan(
            self.organization.uuid, data, self.owner_token
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(content_data["message"], "Invalid plan choice")

    def tearDown(self):
        self.project.delete()
        self.organization.delete()


class OrgBillingAdditionalInformation(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.admin, self.admin_token = create_user_and_token("admin")
        self.contributor, self.contributor_token = create_user_and_token("contributor")
        self.financial, self.financial_token = create_user_and_token("financial")

        self.organization = Organization.objects.create(
            name="test organization",
            description="",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="enterprise",
        )

        self.admin_organization_authorization = self.organization.authorizations.create(
            user=self.admin, role=OrganizationRole.ADMIN.value
        )

        self.contributor_organization_authorization = (
            self.organization.authorizations.create(
                user=self.contributor, role=OrganizationRole.CONTRIBUTOR.value
            )
        )

        self.financial_organization_authorization = (
            self.organization.authorizations.create(
                user=self.financial, role=OrganizationRole.FINANCIAL.value
            )
        )

    def request(self, value, data={}, token=None):
        authorization_header = (
            {"HTTP_AUTHORIZATION": "Token {}".format(token.key)} if token else {}
        )
        request = self.factory.post(
            f"/v1/organization/org/billing/add-additional-information/{value}/",
            **authorization_header,
            data=data,
        )
        response = OrganizationViewSet.as_view(
            {"post": "add_additional_billing_information"}
        )(request, organization_uuid=self.organization.uuid)

        if type(response) == JsonResponse:
            content_data = json.loads(response.content)
            return response, content_data

        response.render()
        content_data = json.loads(response.content)
        return response, content_data

    def test_add_aditional_info(self):
        data = {
            "personal_identification_number": "111.111.111-11",
            "additional_data": "data",
        }
        response, content_data = self.request(
            self.organization.uuid, data, self.admin_token
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(content_data["status"], "SUCCESS")

    def test_add_aditional_info_contributor(self):
        data = {
            "personal_identification_number": "111.111.111-11",
            "additional_data": "This will fail",
        }
        response, content_data = self.request(
            self.organization.uuid, data, self.contributor_token
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_add_aditional_info_financial(self):
        data = {
            "personal_identification_number": "111.111.111-11",
            "additional_data": "This will fail also",
        }
        response, content_data = self.request(
            self.organization.uuid, data, self.financial_token
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_add_additional_info_void_fields(self):
        data = {}
        response, content_data = self.request(
            self.organization.uuid, data, self.admin_token
        )
        self.assertEqual(content_data["status"], "NO CHANGES")

    def tearDown(self):
        self.organization.delete()


class ListOrganizationAuthorizationTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

        self.owner, self.owner_token = create_user_and_token("owner")
        self.user, self.user_token = create_user_and_token()

        self.organization = Organization.objects.create(
            name="test organization",
            description="",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="free",
        )
        self.organization_authorization = self.organization.authorizations.create(
            user=self.owner, role=OrganizationRole.ADMIN.value
        )

        self.user_auth = self.organization.get_user_authorization(self.user)
        self.user_auth.role = OrganizationRole.CONTRIBUTOR.value
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
            name="test organization",
            description="",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="free",
        )
        self.organization_authorization = self.organization.authorizations.create(
            user=self.owner, role=OrganizationRole.ADMIN.value
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
            {"role": OrganizationRole.CONTRIBUTOR.value},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(content_data.get("role"), OrganizationRole.CONTRIBUTOR.value)

        user_authorization = self.organization.get_user_authorization(self.user)
        self.assertEqual(user_authorization.role, OrganizationRole.CONTRIBUTOR.value)

    def test_forbidden(self):
        response, content_data = self.request(
            self.organization,
            self.user_token,
            self.user,
            {"role": OrganizationRole.CONTRIBUTOR.value},
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_t_set_your_role(self):
        response, content_data = self.request(
            self.organization,
            self.owner_token,
            self.owner,
            {"role": OrganizationRole.CONTRIBUTOR.value},
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class DestroyAuthorizationRoleTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

        self.owner, self.owner_token = create_user_and_token("owner")
        self.user, self.user_token = create_user_and_token()

        self.organization = Organization.objects.create(
            name="test organization",
            description="",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="free",
        )
        self.organization_authorization = self.organization.authorizations.create(
            user=self.owner, role=OrganizationRole.ADMIN.value
        )

        self.user_organization_authorization = self.organization.authorizations.create(
            user=self.user, role=OrganizationRole.CONTRIBUTOR.value
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
            name="test organization",
            description="",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="free",
        )
        self.enterprise_org = Organization.objects.create(
            name="test organization enterprise",
            description="",
            inteligence_organization=2,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="enterprise",
        )
        self.custom_org = Organization.objects.create(
            name="test organization custom",
            description="",
            inteligence_organization=3,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="custom",
        )

        self.project = Project.objects.create(
            name="Unit Test Project",
            flow_organization=uuid4.uuid4(),
            organization_id=self.organization.uuid,
        )

        self.organization_authorization = self.organization.authorizations.create(
            user=self.owner, role=OrganizationRole.ADMIN.value
        )

        self.organization_authorization_enterprise = (
            self.enterprise_org.authorizations.create(
                user=self.owner, role=OrganizationRole.ADMIN.value
            )
        )

        self.organization_authorization_enterprise = (
            self.custom_org.authorizations.create(
                user=self.owner, role=OrganizationRole.ADMIN.value
            )
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
        if method == "GET":
            request = self.factory.get(
                f"/v1/organization/org/billing/{param}/", **authorization_header
            )

            response = OrganizationViewSet.as_view({"get": "active_contacts_limit"})(
                request
            )
        else:
            request = self.factory.patch(
                f"/v1/organization/org/billing/{param}/",
                **authorization_header,
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
            name="Unit Test Project 2",
            flow_organization=uuid4.uuid4(),
            organization_id=self.organization.uuid,
            contact_count=250,
        )
        response, content_data = self.request(
            "organization-on-limit",
            self.organization.uuid,
            self.owner_token,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual("free plan isn't longer valid", content_data["message"])

    def test_organization_limit_custom(self):
        response, content_data = self.request(
            "organization-on-limit",
            self.custom_org.uuid,
            self.owner_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            "Your plan don't have a contact active limit", content_data["message"]
        )

    def test_organization_limit_enterprise(self):
        response, content_data = self.request(
            "organization-on-limit",
            self.enterprise_org.uuid,
            self.owner_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            "Your plan don't have a contact active limit", content_data["message"]
        )

    def test_get_active_contacts_limit(self):
        response, content_data = self.request2(
            "active-contacts-limit",
            "GET",
            self.owner_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(content_data["active_contacts_limit"], 200)

    def tearDown(self):
        self.project.delete()
        self.organization.delete()


class ExtraIntegrationsTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

        self.owner, self.owner_token = create_user_and_token("owner")
        self.user, self.user_token = create_user_and_token()
        self.organization = Organization.objects.create(
            name="test organization",
            description="",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="free",
            extra_integration=4,
        )

        self.project = Project.objects.create(
            name="Unit Test Project",
            flow_organization="57257d94-e54b-4ec1-8952-113a81610465",
            organization_id=self.organization.uuid,
        )

        self.organization_authorization = self.organization.authorizations.create(
            user=self.owner, role=OrganizationRole.ADMIN.value
        )

    def request(self, value, param, token=None):
        authorization_header = (
            {"HTTP_AUTHORIZATION": "Token {}".format(token.key)} if token else {}
        )
        request = self.factory.get(
            f"/v1/organization/org/billing/{value}/{param}", **authorization_header
        )
        response = OrganizationViewSet.as_view(
            {"get": "get_extra_active_integrations"}
        )(request, organization_uuid=self.organization.uuid)

        content_data = json.loads(response.content)

        return response, content_data

    def test_extra_integration(self):
        response, content_data = self.request(
            "extra-integrations",
            self.organization.uuid,
            self.owner_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class GetOrganizationStripeDataTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.owner, self.owner_token = create_user_and_token("owner")

        self.organization = Organization.objects.create(
            name="test organization",
            description="",
            inteligence_organization=1,
            organization_billing__cycle=BillingPlan.BILLING_CYCLE_MONTHLY,
            organization_billing__plan="enterprise",
        )
        self.organization.organization_billing.stripe_customer = "cus_KzFc41F3yLCLoO"
        self.organization.organization_billing.save()
        self.organization_authorization = self.organization.authorizations.create(
            user=self.owner, role=OrganizationRole.ADMIN.value
        )

    def request(self, param, value, token=None):
        authorization_header = (
            {"HTTP_AUTHORIZATION": "Token {}".format(token.key)} if token else {}
        )

        request = self.factory.get(
            f"/v1/organization/org/{param}/{value}/", **authorization_header
        )
        response = OrganizationViewSet.as_view({"get": "get_stripe_card_data"})(
            request, organization_uuid=self.organization.uuid
        )

        content_data = json.loads(response.content)
        return (response, content_data)

    def test_get_stripe_card_data(self):
        response, content_data = self.request(
            "get-stripe-card-data",
            self.organization.uuid,
            self.owner_token,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(content_data["response"][0]["last2"], "42")
        self.assertEqual(content_data["response"][0]["brand"], "visa")


class BillingPrecificationAPITestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.owner, self.owner_token = create_user_and_token("owner")

    def request(self, token=None):
        authorization_header = (
            {"HTTP_AUTHORIZATION": "Token {}".format(token.key)} if token else {}
        )

        request = self.factory.get(
            "/v1/organization/org/billing/precification", **authorization_header
        )

        response = OrganizationViewSet.as_view({"get": "get_billing_precification"})(
            request
        )

        content_data = json.loads(response.content)
        return (response, content_data)

    def test_okay(self):
        response, content_data = self.request(
            self.owner_token,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(content_data["currency"], "USD")
        self.assertEqual(
            content_data["extra_whatsapp_integration"],
            settings.BILLING_COST_PER_WHATSAPP,
        )
