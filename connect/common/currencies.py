from functools import lru_cache

import pycountry


@lru_cache(maxsize=1)
def list_currency_codes() -> tuple:
    """ISO 4217 alpha-3 codes, sorted. Cached because pycountry's dataset is static per process."""
    return tuple(sorted(currency.alpha_3 for currency in pycountry.currencies))


def is_valid_currency(code: str) -> bool:
    return code in list_currency_codes()
