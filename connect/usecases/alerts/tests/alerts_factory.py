import factory
import uuid as uuid4

from connect.alerts.models import Alert


class AlertFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Alert

    can_be_closed = True
    text = factory.Sequence(lambda n: "test%d" % n)
    type = 1
    uuid = uuid4.uuid4()
