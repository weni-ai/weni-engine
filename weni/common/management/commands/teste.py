from django.core.management.base import BaseCommand

from weni.billing import get_gateway


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        gateway = get_gateway("stripe")
        gateway.purchase("", "")
