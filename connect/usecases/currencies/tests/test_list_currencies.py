from django.test import SimpleTestCase

from connect.common.currencies import list_currency_codes
from connect.usecases.currencies.list_currencies import ListCurrenciesUseCase


class ListCurrenciesUseCaseTestCase(SimpleTestCase):
    def test_execute_returns_iso_4217_codes(self):
        codes = ListCurrenciesUseCase().execute()

        self.assertEqual(codes, list_currency_codes())
        self.assertIn("BRL", codes)
        self.assertTrue(all(len(code) == 3 for code in codes))
