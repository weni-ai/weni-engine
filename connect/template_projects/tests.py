from django.test import TestCase
from connect.template_projects.models import TemplateType, TemplateFeature, TemplateFlow
from connect.template_projects.storage import TemplateFlowFileStorage, TemplateTypeImageStorage
from unittest.mock import MagicMock


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
            feature_identifier="chatgpt",
            type="text"
        )
        self.template_feature_object.template_type.add(self.template_type_object)

    def test_str(self):

        str_response = self.template_feature_object.__str__()
        model_id = self.template_feature_object.id
        self.assertListEqual(str_response.split(), [str(model_id)])


class TemplateFlowModelTestCase(TestCase):

    def setUp(self):

        self.template_type_object = TemplateType.objects.create(
            level=1,
            category="category",
            description="description",
            name="name",
            setup={"setup": "setup"}
        )

        file_mock = MagicMock(spec="File")
        file_mock.name = 'test_file.json'

        self.template_flow_object = TemplateFlow.objects.create(
            name="name",
            flow_url=file_mock,
            template_type=self.template_type_object
        )

    def test_str(self):

        str_response = self.template_flow_object.__str__()
        model_id = self.template_flow_object.id
        self.assertListEqual(str_response.split(), [str(model_id)])


class StorageTestCase(TestCase):

    def setUp(self):

        self.file_storage = TemplateFlowFileStorage()
        self.image_storage = TemplateTypeImageStorage()

    def test_flow_get_available_name(self):

        file_mock = MagicMock(spec="File")
        file_mock.name = 'test.json'

        response = self.file_storage.get_available_name(file_mock.name)
        self.assertIsNotNone(response)
        self.assertEqual(response.split("_")[0], file_mock.name.split(".")[0])

    def test_type_get_available_name_image(self):

        file_mock = MagicMock(spec="File")
        file_mock.name = 'test.png'

        response = self.image_storage.get_available_name(file_mock.name)
        self.assertIsNotNone(response)
        self.assertEqual(response.split("_")[0], "av")
