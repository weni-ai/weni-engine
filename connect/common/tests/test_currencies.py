from django.test import SimpleTestCase

from connect.common.currencies import is_valid_currency, list_currency_codes


class CurrenciesHelperTestCase(SimpleTestCase):
    def test_list_currency_codes_is_sorted_and_includes_iso_codes(self):
        codes = list_currency_codes()

        self.assertIn("BRL", codes)
        self.assertIn("USD", codes)
        self.assertIn("EUR", codes)
        self.assertEqual(codes, tuple(sorted(codes)))

    def test_is_valid_currency_accepts_known_codes(self):
        self.assertTrue(is_valid_currency("BRL"))
        self.assertTrue(is_valid_currency("USD"))

    def test_is_valid_currency_rejects_unknown_codes(self):
        self.assertFalse(is_valid_currency("ZZZ"))
        self.assertFalse(is_valid_currency(""))
