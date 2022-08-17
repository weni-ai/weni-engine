import string
import random
import pendulum
import datetime
from uuid import uuid4
from weni.protobuf.flows import billing_pb2


class ContactDetail:

    def __init__(self, before, after):
        self.before = before
        self.after = after

    def random_date(self):
        """Generate a random datetime between `start` and `end`"""
        return self.after + datetime.timedelta(
            # Get a random amount of seconds between `start` and `end`
            seconds=random.randint(0, int((self.before - self.after).total_seconds())),
        )

    @staticmethod
    def rando_string():
        letters = string.ascii_letters
        return f"{''.join(random.choice(letters) for i in range(10))}, {''.join(random.choice(letters) for i in range(10))} {''.join(random.choice(letters) for i in range(10))}"

    @staticmethod
    def direction():
        direction = ["OUTPUT", "INPUT"]
        return random.choice(direction)

    @staticmethod
    def random_name():
        letters = string.ascii_letters
        return "".join(random.choice(letters) for i in range(10))

    def sent_on(self):
        random_date = self.random_date()
        seconds, nanos = str(pendulum.instance(random_date).timestamp()).split(".")
        return {"seconds": int(seconds), "nanos": int(nanos)}

    def message(self):
        object = billing_pb2.Msg(
            uuid=str(uuid4()),
            text=self.rando_string(),
            sent_on=self.sent_on(),
            direction=self.direction(),
        )
        return object

    def channel(self):
        object = billing_pb2.Channel(uuid=str(uuid4()), name=self.rando_string())
        return object

    def active_contact(self, channel):
        object = billing_pb2.ActiveContactDetail(
            uuid=str(uuid4()),
            name=self.random_name(),
            msg=self.message(),
            channel=channel,
        )
        return object


def get_active_contacts(project_uuid, before, after):
    response = list()
    before = pendulum.parse(before)
    after = pendulum.parse(after)

    create_contact = ContactDetail(before, after)
    channel = create_contact.channel()
    for i in range(10):
        if i == 5:
            channel = create_contact.channel()
        contact = create_contact.active_contact(channel)
        response.append(contact)
    return response
