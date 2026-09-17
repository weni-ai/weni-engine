from django.test import SimpleTestCase

from connect.api.v2.projects.serializers import ProjectUpdateSerializer


class ProjectUpdateSerializerCurrencyTestCase(SimpleTestCase):
    def test_normalizes_currency_code(self):
        serializer = ProjectUpdateSerializer(data={"currency": "brl"})

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["currency"], "BRL")

    def test_rejects_unknown_currency(self):
        serializer = ProjectUpdateSerializer(data={"currency": "ZZZ"})

        self.assertFalse(serializer.is_valid())
        self.assertIn("currency", serializer.errors)

    def test_allows_null_currency(self):
        serializer = ProjectUpdateSerializer(data={"currency": None})

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIsNone(serializer.validated_data["currency"])
