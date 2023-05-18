from django.test import TestCase
from connect.template_projects.models import TemplateType, TemplateAI, TemplateFeature


class TemplateTypeModelTestCase(TestCase):

    def setUp(self):

        self.template_type_object = TemplateType.objects.create(
            level=1,
            category="category",
            description="description",
            name="name",
            setup={"setup": "setup"}
        )

    def test_str(self):

        str_response = self.template_type_object.__str__()
        model_id = self.template_type_object.id
        self.assertListEqual(str_response.split(), [str(model_id)])


class TemplateAIModelTestCase(TestCase):

    def setUp(self):

        self.template_type_object = TemplateType.objects.create(
            level=1,
            category="category",
            description="description",
            name="name",
            setup={"setup": "setup"}
        )

        self.template_ai_object = TemplateAI.objects.create(
            name="name",
            description="description",
            template_type=self.template_type_object
        )

    def test_str(self):

        str_response = self.template_ai_object.__str__()
        model_id = self.template_ai_object.id
        self.assertListEqual(str_response.split(), [str(model_id)])


class TemplateFeatureModelTestCase(TestCase):

    def setUp(self):

        self.template_type_object = TemplateType.objects.create(
            level=1,
            category="category",
            description="description",
            name="name",
            setup={"setup": "setup"}
        )

        self.template_feature_object = TemplateFeature.objects.create(
            name="name",
            description="description",
            type="type",
            feature_identifier="feature_identifier",
            template_type=self.template_type_object
        )

    def test_str(self):

        str_response = self.template_feature_object.__str__()
        model_id = self.template_feature_object.id
        self.assertListEqual(str_response.split(), [str(model_id)])
