import uuid
import random
import pendulum
from rest_framework.authtoken.models import Token

from connect.authentication.models import User
from connect.common.models import Project
from connect.billing.models import Contact


def create_user_and_token(nickname="fake"):
    user = User.objects.create_user("{}@user.com".format(nickname), nickname)
    token, create = Token.objects.get_or_create(user=user)
    return user, token


def create_contacts(num_contacts: int, day=None):
    """This function creates contacts that were active multiple times a day."""
    if not day:
        day = pendulum.now().start_of("day")

    contact_list = []

    for project in Project.objects.all():
        for j in range(0, num_contacts):
            if j == 0 or j % 5 == 0:
                contact_flow_uuid = uuid.uuid4()
                last_seen_on = day.add(hours=random.randint(0, 23))
                last_seen_on2 = day.add(days=1).add(hours=random.randint(0, 23))
                last_seen_on3 = day.add(days=2).add(hours=random.randint(0, 23))

            contact = Contact(
                contact_flow_uuid=contact_flow_uuid,
                last_seen_on=last_seen_on,
                project=project,
            )
            contact2 = Contact(
                contact_flow_uuid=contact_flow_uuid,
                last_seen_on=last_seen_on2,
                project=project,
            )
            contact3 = Contact(
                contact_flow_uuid=contact_flow_uuid,
                last_seen_on=last_seen_on3,
                project=project,
            )

            contact_list.extend([contact, contact2, contact3])

    Contact.objects.bulk_create(contact_list)
