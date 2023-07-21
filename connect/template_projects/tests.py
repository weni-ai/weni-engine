import uuid
from storages.backends.s3boto3 import S3Boto3Storage
from django.test import TestCase
from unittest.mock import patch
from connect.storages import AvatarUserMediaStorage
from connect.template_projects.storage import TemplateTypeImageStorage
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


class StorageTestCase(TestCase):

    @patch.object(S3Boto3Storage, 'get_available_name')
    def test_avatar_storage_get_available_name_with_override(self, mock_get_available_name):
        storage = AvatarUserMediaStorage()
        storage.override_available_name = True

        ext = "png"
        filename = "av_%s.%s" % (uuid.uuid4(), ext)
        mock_get_available_name.return_value = filename

        name = "example.png"
        max_length = 100

        result = storage.get_available_name(name, max_length)

        mock_get_available_name.assert_called_once()

        args, kwargs = mock_get_available_name.call_args
        self.assertTrue(args[0].startswith("av_"))
        self.assertEqual(args[1], max_length)

        self.assertEqual(result, filename)

    @patch.object(S3Boto3Storage, 'get_available_name')
    def test_template_storage_get_available_name_with_override(self, mock_get_available_name):
        storage = TemplateTypeImageStorage()
        storage.override_available_name = True

        ext = "png"
        filename = "av_%s.%s" % (uuid.uuid4(), ext)
        mock_get_available_name.return_value = filename

        name = "example.png"
        max_length = 100

        result = storage.get_available_name(name, max_length)

        mock_get_available_name.assert_called_once()

        args, kwargs = mock_get_available_name.call_args
        self.assertTrue(args[0].startswith("av_"))
        self.assertEqual(args[1], max_length)

        self.assertEqual(result, filename)