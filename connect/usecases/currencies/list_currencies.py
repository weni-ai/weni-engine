from connect.common.currencies import list_currency_codes


class ListCurrenciesUseCase:
    def execute(self) -> tuple:
        return list_currency_codes()
