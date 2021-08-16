import datetime

from django.core.management.base import BaseCommand
from google.protobuf.timestamp_pb2 import Timestamp

from weni import utils
from weni.common.models import Invoice, BillingPlan


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        # gateway = get_gateway("stripe")
        # gateway.purchase(5, "cus_Jvmmq0P9aEP8Fw", {"id": 26})

        # timestamp = Timestamp()
        #
        # flow_instance = utils.get_grpc_types().get("flow")
        # x = flow_instance.get_billing_total_statistics(
        #     project_uuid="459997b6-22d8-4885-818a-665801ba8aff",
        #     before=timestamp.FromDatetime(
        #         datetime.datetime.strptime("2020-08-01", "%Y-%m-%d")
        #     ),
        #     after=timestamp.FromDatetime(datetime.datetime.now()),
        # )
        # x = Invoice.objects.get(pk=7).calculate_amount(1)
        # x = Invoice.objects.get(pk=8).total_invoice_amount
        # print(x)
        x = BillingPlan.objects.get(pk=2).remove_credit_card
