import json
import uuid as uuid4
from unittest.mock import patch, Mock, MagicMock
from django.conf import settings
from django.http import JsonResponse
from django.test import RequestFactory
from django.test import TestCase
from django.test.client import MULTIPART_CONTENT
from rest_framework import status
from connect.api.v1.organization.serializers import RequestPermissionOrganizationSerializer
from connect.authentication.models import User
from rest_framework.exceptions import ValidationError
from connect.api.v1.organization.views import (
    OrganizationAuthorizationViewSet,
)
from connect.api.v1.tests.utils import create_user_and_token
from connect.common.models import (
    Organization,
)
from connect.api.v1.organization.views import (
    RequestPermissionOrganizationViewSet,
)


class MockPublisher:
    def send_message(self, message_body, exchange="orgs-auths.topic", routing_key=""):
        print(message_body)
        pass


class CreateOrganizationAuthorizationTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.org = Organization.objects.create(
            name="Org Teste",
            description="Org Teste",
            organization_billing__plan="enterprise",
            organization_billing__cycle="monthly",
        )
        self.project = self.org.project.create(name="Project Teste")

        self.owner, self.owner_token = create_user_and_token("owner")
        self.owner_auth = self.org.authorizations.create(user=self.owner, role=3)

        self.user, self.user_token = create_user_and_token("user")

    # @patch("connect.common.models.RabbitmqPublisher")
    def test_request_permission_organization(self):
        print("[+] test_request_permission_organization [+]")
        publisher = MockPublisher
        authorization_header = (
            {"HTTP_AUTHORIZATION": "Token {}".format(self.owner_token.key)}
        )

        data = {
            "organization": str(self.org.uuid),
            "email": self.user.email,
            "role": 3
        }
        request = self.factory.post(
            "/v1/organization/request-permission/", data, **authorization_header
        )
        response = RequestPermissionOrganizationViewSet.as_view({"post": "create"})(request)
        response.render()
        content_data = json.loads(response.content)
        self.assertEquals(response.status_code, 201)

    def test_update_organization_authorization(self):
        print("[+] test_update_organization_authorization [+]")

        self.user_auth = self.org.authorizations.create(user=self.user, role=3)
        self.project.project_authorizations.create(
            user=self.user,
            role=3,
            organization_authorization=self.user_auth
        )
        authorization_header = (
            {"HTTP_AUTHORIZATION": "Token {}".format(self.owner_token.key), "Content-Type": "application/json"}
        )

        data = {"role": 2}

        request = self.factory.patch(
            f"/organization/authorizations/{str(self.org.uuid)}/{self.user.id}/",
            data,
            content_type="application/json",
            format="json",
            **authorization_header,
        )

        response = OrganizationAuthorizationViewSet.as_view({"patch": "update"})(
            request,
            organization__uuid=str(self.org.uuid),
            user__id=self.user.id
        )

        response.render()
        content_data = json.loads(response.content)

        self.assertEquals(response.status_code, 200)
        self.assertEquals(content_data.get("role"), 2)
