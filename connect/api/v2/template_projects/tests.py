import json
import unittest

from django.test import RequestFactory, TestCase

from connect.api.v1.tests.utils import create_user_and_token
from connect.template_projects.models import (
    TemplateFeature,
    TemplateSuggestion,
    TemplateType,
)

from .views import (
    TemplateFeatureViewSet,
    TemplateSuggestionViewSet,
    TemplateTypeViewSet,
)


@unittest.skip("Test broken, need to be fixed")
class TemplateTypeViewSetTestCase(TestCase):
    def setUp(self):

        self.factory = RequestFactory()
        self.owner, self.owner_token = create_user_and_token("owner")

        self.template_type_object = TemplateType.objects.create(
            level=1, category=["category"], description="description", name="name"
        )

    def request(self, method, url, data=None, user=None, token=None, id=None):

        headers = {"HTTP_AUTHORIZATION": "Token {}".format(token.key)} if token else {}

        request = self.factory.request(method=method, path=url, data=data, **headers)
        response = TemplateTypeViewSet.as_view(method)(request, pk=id)
        response.render()
        content_data = json.loads(response.content)

        return content_data

    def test_get_queryset(self):

        response = self.request(
            {"get": "list"},
            "/v2/projects/template-type",
            user=self.owner,
            token=self.owner_token,
        )
        self.assertEqual(response["count"], 1)
        response = self.request(
            {"get": "list"},
            "/v2/projects/template-type?name=name",
            user=self.owner,
            token=self.owner_token,
        )
        self.assertEqual(response["count"], 1)
        response = self.request(
            {"get": "list"},
            "/v2/projects/template-type?category=category",
            user=self.owner,
            token=self.owner_token,
        )
        self.assertEqual(response["count"], 1)
        response = self.request(
            {"get": "list"},
            "/v2/projects/template-type?id=1",
            user=self.owner,
            token=self.owner_token,
        )
        self.assertEqual(response["count"], 1)
        obj_uuid = self.template_type_object.uuid
        response = self.request(
            {"get": "list"},
            f"/v2/projects/template-type?uuid={obj_uuid}",
            user=self.owner,
            token=self.owner_token,
        )
        self.assertEqual(response["count"], 1)

    def test_retrieve(self):

        template_id = self.template_type_object.id

        response = self.request(
            {"get": "retrieve"},
            f"/v2/projects/template-type/{template_id}",
            user=self.owner,
            token=self.owner_token,
            id=template_id,
        )
        self.assertEqual(response["name"], "name")


@unittest.skip("Test broken, need to be fixed")
class TemplateFeatureViewSetTest(TestCase):
    def setUp(self):

        self.factory = RequestFactory()
        self.owner, self.owner_token = create_user_and_token("owner")

        self.template_type_object = TemplateType.objects.create(
            level=1, category=["category"], description="description", name="name"
        )

        self.template_feature_object = TemplateFeature.objects.create(
            name="name",
            description="description",
            template_type=self.template_type_object,
            feature_identifier="chatgpt",
            type="text",
        )

    def request(self, method, url, data=None, user=None, token=None, id=None):

        headers = {"HTTP_AUTHORIZATION": "Token {}".format(token.key)} if token else {}

        request = self.factory.request(method=method, path=url, data=data, **headers)
        response = TemplateFeatureViewSet.as_view(method)(request, pk=id)
        response.render()
        content_data = json.loads(response.content)

        return content_data

    def test_get_queryset(self):

        response = self.request(
            {"get": "list"},
            "/v2/projects/template-feature",
            user=self.owner,
            token=self.owner_token,
        )
        self.assertEqual(response["count"], 1)
        response = self.request(
            {"get": "list"},
            "/v2/projects/template-feature?name=name",
            user=self.owner,
            token=self.owner_token,
        )
        self.assertEqual(response["count"], 1)
        response = self.request(
            {"get": "list"},
            "/v2/projects/template-feature?template_type=1",
            user=self.owner,
            token=self.owner_token,
        )
        self.assertEqual(response["count"], 1)


@unittest.skip("Test broken, need to configure rabbitmq")
class TemplateSuggestionViewSetTest(TestCase):
    def setUp(self):

        self.factory = RequestFactory()
        self.owner, self.owner_token = create_user_and_token("owner")

        self.template_suggestion_object = TemplateSuggestion.objects.create(
            suggestion="suggestion", type="type", status="status"
        )

    def request(self, method, url, data=None, user=None, token=None, id=None):

        headers = {"HTTP_AUTHORIZATION": "Token {}".format(token.key)} if token else {}
        if method == {"post": "create"}:
            request = self.factory.post(
                path=url, data=data, **headers, content_type="application/json"
            )
        else:
            request = self.factory.request(
                method=method, path=url, data=data, **headers
            )
        response = TemplateSuggestionViewSet.as_view(method)(request, pk=id)
        response.render()
        content_data = json.loads(response.content)
        return content_data

    def test_get_queryset_suggestion_endpoints(self):

        response = self.request(
            {"get": "list"},
            "/v2/projects/template-suggestion",
            user=self.owner,
            token=self.owner_token,
        )
        self.assertEqual(response["count"], 1)
        response = self.request(
            {"get": "list"},
            "/v2/projects/template-suggestion?id=1",
            user=self.owner,
            token=self.owner_token,
        )
        self.assertEqual(response["count"], 1)

    def test_post_endpoint(self):

        data = {"suggestion": "test 2", "type": "template", "status": "pending"}
        response = self.request(
            {"post": "create"},
            "/v2/projects/template-suggestion",
            user=self.owner,
            token=self.owner_token,
            data=data,
        )
        self.assertEqual(response["suggestion"], data["suggestion"])
