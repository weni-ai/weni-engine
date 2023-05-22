from django.test import TestCase

from rest_framework.serializers import ValidationError
from .serializers import ListClassifierSerializer


class ListClassifierSerializerTest(TestCase):
    def test_validate_project_uuid(self):
        serializer = ListClassifierSerializer()

        # Teste com entrada inválida
        invalid_uuid = 1
        with self.assertRaises(ValidationError) as context:
            serializer.validate_project_uuid(invalid_uuid)
        error_detail = str(context.exception.detail[0])
        self.assertEqual(
            error_detail,
            'This project does not exist'
        )
