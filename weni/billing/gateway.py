from importlib import import_module
from typing import Any

from django.conf import settings

gateway_cache = {}


class GatewayModuleNotFound(Exception):
    pass


class GatewayNotConfigured(Exception):
    pass


class Gateway(object):
    """Sub-classes to inherit from this and implement the below methods"""

    # To indicate if the gateway is in test mode or not
    test_mode = getattr(settings, "BILLING_TEST_MODE", False)

    # The below are optional attributes to be implemented and used by subclases.
    #
    # Set to indicate the default currency for the gateway.
    default_currency = ""
    # Name of the gateway.
    display_name = ""

    def purchase(self, money: float, identification: Any, options: dict = None):
        """
        One go authorize and capture transaction
        :return: {'status': 'SUCCESS', 'response': response}
        """
        raise NotImplementedError

    def authorize(self, money: float, identification: Any, options: dict = None):
        """
        Authorization for a future capture transaction
        :return: {'status': "SUCCESS", "response": response}
        """
        raise NotImplementedError

    def capture(self, money: float, authorization: Any, options: dict = None):
        """
        Capture funds from a previously authorized transaction
        :return: {'status': "SUCCESS", "response": response}
        """
        raise NotImplementedError

    def credit(self, money: float, identification: Any, options: dict = None):
        """
        Refund a previously 'settled' transaction
        :return: {'status': "SUCCESS", "response": response}
        """
        raise NotImplementedError

    def unstore(self, identification: Any, options: dict = None):
        """
        Delete the previously stored credit card and user
        profile information on the gateway
        :return: {'status': "SUCCESS", "response": response}
        """
        raise NotImplementedError


def get_gateway(gateway, *args, **kwargs):
    """
    Return a gateway instance specified by `gateway` name.
    This caches gateway classes in a module-level dictionnary to avoid hitting
    the filesystem every time we require a gateway.

    Should the list of available gateways change at runtime, one should then
    invalidate the cache, the simplest of ways would be to:

    >>> gateway_cache = {}
    """
    # Is the class in the cache?
    instance = gateway_cache.get(gateway, None)
    if not instance:
        # Let's actually load it (it's not in the cache)
        gateway_filename = "%s_gateway" % gateway
        gateway_module = None
        for app in settings.INSTALLED_APPS:
            try:
                gateway_module = import_module(
                    f".gateways.{gateway_filename}", package=app
                )
            except ImportError:
                pass
        if not gateway_module:
            raise GatewayModuleNotFound(f"Missing gateway: {gateway}")
        gateway_class_name = "".join(gateway_filename.title().split("_"))
        try:
            instance = getattr(gateway_module, gateway_class_name)
        except AttributeError:
            raise GatewayNotConfigured(
                f"Missing {gateway_class_name} class in the gateway module."
            )
        gateway_cache[gateway] = instance
    # We either hit the cache or load our class object, let's return an instance
    # of it.
    return instance(*args, **kwargs)
