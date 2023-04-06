import json
from django.test import TestCase, RequestFactory
from connect.template_projects.models import TemplateType
from connect.api.v1.tests.utils import create_user_and_token
from connect.api.v2.template_projects.views import TemplateTypeViewSet

# Create your tests here.


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

    def test_retrieve(self):

        template_id = self.template_type_object.id

        print("Object id:", self.template_type_object.id)
        response = self.request(
            {"get": "retrieve"},
            f"/v2/projects/template-type/{template_id}",
            user=self.owner,
            token=self.owner_token,
            id=template_id
        )
        self.assertEqual(response["name"], "name")
