from django.core.management.base import BaseCommand

from weni.billing import get_gateway


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        gateway = get_gateway("stripe")
        gateway.purchase(5, "cus_Jvmmq0P9aEP8Fw", {"id": 26})
