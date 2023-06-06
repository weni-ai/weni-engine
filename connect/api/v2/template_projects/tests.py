
import json
from django.test import TestCase, RequestFactory
from unittest.mock import MagicMock
from .views import TemplateTypeViewSet, TemplateFeatureViewSet, TemplateFlowViewSet

from connect.api.v1.tests.utils import create_user_and_token
from connect.template_projects.models import TemplateType, TemplateFeature, TemplateFlow


class TemplateTypeViewSetTestCase(TestCase):

    def setUp(self):

        self.factory = RequestFactory()
        self.owner, self.owner_token = create_user_and_token("owner")

        self.template_type_object = TemplateType.objects.create(
            level=1,
            category="category",
            description="description",
            name="name"
        )

    def request(self, method, url, data=None, user=None, token=None, id=None):

        headers = {"HTTP_AUTHORIZATION": "Token {}".format(token.key)} if token else {}

        request = self.factory.request(method=method, path=url, data=data, **headers)
        response = TemplateTypeViewSet.as_view(method)(request, pk=id)
        response.render()
        content_data = json.loads(response.content)

        return content_data

    def test_get_queryset(self):

        response = self.request({"get": "list"}, "/v2/projects/template-type", user=self.owner, token=self.owner_token)
        self.assertEqual(response["count"], 1)
        response = self.request({"get": "list"}, "/v2/projects/template-type?name=name", user=self.owner, token=self.owner_token)
        self.assertEqual(response["count"], 1)
        response = self.request({"get": "list"}, "/v2/projects/template-type?category=category", user=self.owner, token=self.owner_token)
        self.assertEqual(response["count"], 1)
        response = self.request({"get": "list"}, "/v2/projects/template-type?id=1", user=self.owner, token=self.owner_token)
        self.assertEqual(response["count"], 1)

    def test_retrieve(self):

        template_id = self.template_type_object.id

        response = self.request(
            {"get": "retrieve"},
            f"/v2/projects/template-type/{template_id}",
            user=self.owner,
            token=self.owner_token,
            id=template_id
        )
        self.assertEqual(response["name"], "name")


class TemplateFeatureViewSetTest(TestCase):

    def setUp(self):

        self.factory = RequestFactory()
        self.owner, self.owner_token = create_user_and_token("owner")

        self.template_type_object = TemplateType.objects.create(
            level=1,
            category="category",
            description="description",
            name="name"
        )

        self.template_feature_object = TemplateFeature.objects.create(
            name="name",
            description="description",
            feature_identifier="chatgpt",
            type="text"
        )
        self.template_feature_object.template_type.add(self.template_type_object)

    def request(self, method, url, data=None, user=None, token=None, id=None):

        headers = {"HTTP_AUTHORIZATION": "Token {}".format(token.key)} if token else {}

        request = self.factory.request(method=method, path=url, data=data, **headers)
        response = TemplateFeatureViewSet.as_view(method)(request, pk=id)
        response.render()
        content_data = json.loads(response.content)

        return content_data

    def test_get_queryset(self):

        response = self.request({"get": "list"}, "/v2/projects/template-feature", user=self.owner, token=self.owner_token)
        self.assertEqual(response["count"], 1)
        response = self.request({"get": "list"}, "/v2/projects/template-feature?name=name", user=self.owner, token=self.owner_token)
        self.assertEqual(response["count"], 1)
        response = self.request({"get": "list"}, "/v2/projects/template-feature?template_type=1", user=self.owner, token=self.owner_token)
        self.assertEqual(response["count"], 1)


class TemplateFlowViewSetTest(TestCase):

    def setUp(self):

        self.factory = RequestFactory()
        self.owner, self.owner_token = create_user_and_token("owner")

        self.template_type_object = TemplateType.objects.create(
            level=1,
            category="category",
            description="description",
            name="name"
        )

        file_mock = MagicMock(spec="File")
        file_mock.name = 'test_file.json'

        self.template_flow_object = TemplateFlow.objects.create(
            name="name",
            flow_url=file_mock,
            template_type=self.template_type_object
        )

    def request(self, method, url, data=None, user=None, token=None, id=None):

        headers = {"HTTP_AUTHORIZATION": "Token {}".format(token.key)} if token else {}

        request = self.factory.request(method=method, path=url, data=data, **headers)
        response = TemplateFlowViewSet.as_view(method)(request, pk=id)
        response.render()
        content_data = json.loads(response.content)

        return content_data

    def test_get_queryset(self):

        response = self.request({"get": "list"}, "/v2/projects/template-flow", user=self.owner, token=self.owner_token)
        self.assertEqual(response["count"], 1)
        response = self.request({"get": "list"}, "/v2/projects/template-flow?name=name", user=self.owner, token=self.owner_token)
        self.assertEqual(response["count"], 1)
        response = self.request({"get": "list"}, "/v2/projects/template-flow?template_type=1", user=self.owner, token=self.owner_token)
        self.assertEqual(response["count"], 1)
