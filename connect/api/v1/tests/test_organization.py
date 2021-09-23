import json
import uuid as uuid4
from unittest.mock import patch

from django.test import RequestFactory
from django.test import TestCase
from django.test.client import MULTIPART_CONTENT
from rest_framework import status

from connect.api.v1.organization.views import (
    OrganizationViewSet,
    OrganizationAuthorizationViewSet,
)
from connect.api.v1.tests.utils import create_user_and_token
from connect.common.models import Organization, OrganizationAuthorization


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
            name="test organization", description="", inteligence_organization=1
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


class ListOrganizationAuthorizationTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

        self.owner, self.owner_token = create_user_and_token("owner")
        self.user, self.user_token = create_user_and_token()

        self.organization = Organization.objects.create(
            name="test organization", description="", inteligence_organization=1
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
            name="test organization", description="", inteligence_organization=1
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
            name="test organization", description="", inteligence_organization=1
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
