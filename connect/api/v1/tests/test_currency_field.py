from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from connect.api.v1.fields import CurrencyField


class CurrencyFieldTestCase(SimpleTestCase):
    def setUp(self):
        self.field = CurrencyField(required=False, allow_null=True, allow_blank=True)

    def test_lower_case_code_is_normalized(self):
        self.assertEqual(self.field.to_internal_value("brl"), "BRL")

    def test_valid_code_is_accepted(self):
        self.assertEqual(self.field.to_internal_value("USD"), "USD")

    def test_unknown_code_raises_validation_error(self):
        with self.assertRaises(ValidationError):
            self.field.to_internal_value("XYZ")
        with self.assertRaises(ValidationError):
            self.field.to_internal_value("ZZZ")

    def test_empty_value_is_allowed(self):
        self.assertEqual(self.field.to_internal_value(""), "")

    def test_null_value_is_allowed(self):
        self.assertIsNone(self.field.run_validation(None))
